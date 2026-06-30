"""Tests for the publisher-dispatch in `api/publish.py`.

We don't boot FastAPI here — we directly call the helpers `_publish_via_*`
and `_absolute_clip_path` to make sure:
    * method routing picks the right upstream,
    * paths are resolved relative to WORKSPACE_DIR,
    * missing files / missing cookies raise the right HTTPException,
    * publish_log captures the method.

Heavy machinery (ytb-up, OAuth) is mocked per test.
"""
import asyncio
import json
import pytest
from fastapi import HTTPException


def _run(coro):
    return asyncio.run(coro)



@pytest.fixture
def clip():
    return {"id": "clip-1", "file_path": "clip.mp4"}


def test_absolute_clip_path_relative(monkeypatch, tmp_path):
    """Relative clip paths resolve under WORKSPACE_DIR; absolute paths pass through."""
    from backend.api import publish as pub_api
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    rel = pub_api._absolute_clip_path("a/b.mp4")
    assert rel == tmp_path / "a" / "b.mp4"
    abs_path = tmp_path / "abs.mp4"
    abs_path.write_bytes(b"\x00")
    out = pub_api._absolute_clip_path(str(abs_path))
    assert out == abs_path


def test_publish_via_browser_dispatches_to_youtube_browser(
    monkeypatch, clip, tmp_path
):
    from backend.api import publish as pub_api
    cookies = tmp_path / "cookies.json"
    cookies.write_text(json.dumps([
        {"name": "SID", "value": "x", "domain": ".youtube.com",
         "sameSite": "no_restriction"}
    ]))
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 64)

    class _StubReq:
        clip_id = "clip-1"
        title = "t"
        description = "d"
        tags = ["s"]
        cookies_path = None
        account_id = "default"
    # Patch helpers — clip is currently relative to fake WORKSPACE_DIR.
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(pub_api, "COOKIES_DIR", tmp_path / "accounts")
    (tmp_path / "accounts" / "default").mkdir(parents=True)
    # _StubReq.cookies_path=None → defaults to COOKIES_DIR/account_id/cookies.json

    seen = {}
    async def fake_upload(**kwargs):
        seen["called"] = kwargs
        return pub_api.PublishResponse(youtube_url="https://youtu.be/xyz",
                                        status="success", message="ok")

    monkeypatch.setattr(pub_api, "upload_with_cookies", fake_upload)

    res = _run(pub_api._publish_via_browser(clip, _StubReq()))
    assert isinstance(res, pub_api.PublishResponse)
    assert res.status == "success"
    assert seen["called"]["title"] == "t"
    # cookie path was resolved from account_id default.
    assert str(seen["called"]["cookies_path"]).replace("\\", "/").endswith(
        "default/cookies.json"
    )


def test_publish_via_browser_clip_missing_raises_404(monkeypatch, clip, tmp_path):
    """The function raises HTTPException(404) when the clip file is gone."""
    from backend.api import publish as pub_api
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(pub_api, "COOKIES_DIR", tmp_path / "accounts")
    (tmp_path / "accounts" / "default").mkdir(parents=True)
    class _StubReq:
        clip_id = "clip-1"; title = "t"; description = "d"; tags = []
        cookies_path = None; account_id = "default"
    with pytest.raises(HTTPException) as exc:
        _run(pub_api._publish_via_browser(clip, _StubReq()))
    assert exc.value.status_code == 404
    assert "clip" in str(exc.value.detail).lower()


def test_publish_via_browser_logs_method_browser(monkeypatch, clip, tmp_path):
    """save_publish_log is called with method='browser' on success."""
    from backend.api import publish as pub_api
    cookies = tmp_path / "cookies.json"
    cookies.write_text(json.dumps([{"name": "A", "value": "1"}]))
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 64)
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(pub_api, "COOKIES_DIR", tmp_path / "accounts")
    (tmp_path / "accounts" / "default").mkdir(parents=True)
    class _StubReq:
        clip_id = "clip-1"; title = "t"; description = "d"; tags = []
        cookies_path = str(cookies); account_id = None

    async def fake_upload(**_):
        return pub_api.PublishResponse(youtube_url="u", status="success", message="ok")
    monkeypatch.setattr(pub_api, "upload_with_cookies", fake_upload)
    seen_log = {}
    async def fake_log(d):
        seen_log.update(d)
    monkeypatch.setattr(pub_api, "save_publish_log", fake_log)

    _run(pub_api._publish_via_browser(clip, _StubReq()))
    assert seen_log.get("method") == "browser"
