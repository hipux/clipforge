"""Unit tests for the YouTube-Browser publisher adapter.

We never spawn a real browser in CI — the test seam `_driver` lets us pass
a fake `upload` function and observe the PubResult contract.
"""
import asyncio
import json
import pytest
from pathlib import Path

from backend.services import youtube_browser_publisher as ybp


def _run(coro):
    """Run an async coroutine synchronously — convenience for tests."""
    return asyncio.run(coro)



@pytest.fixture
def cookies_path(tmp_path: Path):
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps([
        {"name": "SID", "value": "x", "domain": ".youtube.com", "path": "/",
         "sameSite": "no_restriction", "httpOnly": True, "secure": True},
        {"name": "HSID", "value": "y", "domain": ".youtube.com", "path": "/",
         "sameSite": "Lax"},
    ]))
    return p


@pytest.fixture
def clip_path(tmp_path: Path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\x00" * 32)  # empty placeholder — driver gets path only
    return p


def test_cookies_to_storage_state_normalises_no_restriction(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps([
        {"name": "A", "value": "1", "domain": ".yt.com",
         "sameSite": "no_restriction"},
    ]))
    state = ybp._cookies_to_storage_state(path)
    assert state["cookies"][0]["sameSite"] == "None"


def test_cookies_to_storage_state_passes_through_known_values(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps([
        {"name": "A", "value": "1", "domain": ".yt.com",
         "sameSite": "Lax"},
    ]))
    state = ybp._cookies_to_storage_state(path)
    assert state["cookies"][0]["sameSite"] == "Lax"


def test_cookies_to_storage_state_accepts_dict_shape(tmp_path):
    """Cookie-Editor exports either a list OR `{"cookies": [...]}`."""
    path = tmp_path / "c.json"
    path.write_text(json.dumps({
        "cookies": [
            {"name": "A", "value": "1", "domain": ".yt.com", "sameSite": "Strict"}
        ],
        "origins": [],
    }))
    state = ybp._cookies_to_storage_state(path)
    assert state["cookies"][0]["name"] == "A"


def test_upload_with_cookies_missing_cookies_file_returns_failed(clip_path):
    res = _run(ybp.upload_with_cookies(
        file_path=clip_path, title="t", description="d", tags=[],
        cookies_path=Path("/nonexistent/cookies.json"),
    ))
    assert res.status == "failed"
    assert "cookies" in res.message.lower()


def test_upload_with_cookies_empty_cookies_returns_failed(tmp_path, clip_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps([]))
    res = _run(ybp.upload_with_cookies(
        file_path=clip_path, title="t", description="d", tags=[],
        cookies_path=p,
    ))
    assert res.status == "failed"
    assert "no usable cookies" in res.message.lower()


def test_upload_with_cookes_missing_clip_returns_failed(cookies_path):
    res = _run(ybp.upload_with_cookies(
        file_path=Path("/nonexistent.mp4"), title="t", description="d",
        tags=[], cookies_path=cookies_path,
    ))
    assert res.status == "failed"
    assert "clip" in res.message.lower()


def test_upload_with_cookies_success_calls_driver(cookies_path, clip_path, monkeypatch):
    """_driver fake returns (uploaded=True, url='https://youtu.be/x') -> success."""
    calls = []
    def fake_driver(file_path, title, description, tags, storage_state,
                    profile_dir, proxy, headline_path):
        calls.append({
            "file_path": file_path, "title": title, "description": description,
            "tags": tags, "proxy": proxy,
        })
        return True, "https://youtu.be/abcdefghijk"
    res = _run(ybp.upload_with_cookies(
        file_path=clip_path, title="Banger clip", description="...",
        tags=["shorts", "funny"], cookies_path=cookies_path,
        profile_dir=None, proxy=None, headline_path=None,
        _driver=fake_driver,
    ))
    assert res.status == "success"
    assert res.youtube_url == "https://youtu.be/abcdefghijk"
    assert calls, "driver fake must be invoked exactly once"
    call = calls[0]
    assert call["title"] == "Banger clip"
    assert call["tags"] == ["shorts", "funny"]


def test_upload_with_cookies_failed_upload_returns_no_url(cookies_path, clip_path):
    def fake_driver(**_):
        return False, None
    res = _run(ybp.upload_with_cookies(
        file_path=clip_path, title="x", description="", tags=[],
        cookies_path=cookies_path, _driver=fake_driver,
    ))
    assert res.status == "failed"
    assert res.youtube_url is None


def test_upload_with_cookies_driver_exception_caught(cookies_path, clip_path):
    def fake_driver(**_):
        raise RuntimeError("playwright crashed")
    res = _run(ybp.upload_with_cookies(
        file_path=clip_path, title="x", description="", tags=[],
        cookies_path=cookies_path, _driver=fake_driver,
    ))
    assert res.status == "failed"
    assert "runtime error" in res.message.lower()


def test_upload_with_cookies_proxy_passed_through(cookies_path, clip_path):
    """proxy prop is forwarded to driver (used later for #5 multi-account)."""
    seen = {}
    def fake_driver(file_path, title, description, tags, storage_state,
                    profile_dir, proxy, headline_path):
        seen["proxy"] = proxy
        return True, None
    _run(ybp.upload_with_cookies(
        file_path=clip_path, title="x", description="", tags=[],
        cookies_path=cookies_path, proxy="socks5://user:pw@127.0.0.1:1080",
        _driver=fake_driver,
    ))
    assert seen["proxy"] == "socks5://user:pw@127.0.0.1:1080"
