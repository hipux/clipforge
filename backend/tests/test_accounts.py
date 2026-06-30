"""Tests for backend account CRUD + account-aware publish dispatch.

Pure sync wrappers around aiosqlite calls — we run them with asyncio.run()
to avoid pulling in pytest-asyncio / anyio just for these.
"""
import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.db import (
    create_account, get_account, list_accounts, update_account,
    delete_account, touch_account,
)
from backend.api import publish as pub_api
from backend.api import accounts as acc_api


def _run(coro):
    return asyncio.run(coro)


# ─── Pure DB CRUD ────────────────────────────────────────────────────────────

def test_list_accounts_returns_at_least_default_row():
    rows = _run(list_accounts())
    assert any(r["id"] == "default" for r in rows), rows


def test_create_and_get_account(tmp_path):
    cookies = tmp_path / "c.json"
    cookies.write_text("[]")
    _run(create_account({
        "id": "anime-ch",
        "name": "Anime Channel",
        "platform": "youtube",
        "cookies_path": str(cookies),
        "proxy": None,
        "preferred_preset": "films_anime",
    }))
    row = _run(get_account("anime-ch"))
    assert row is not None
    assert row["name"] == "Anime Channel"
    assert row["preferred_preset"] == "films_anime"
    assert row["cookies_path"] == str(cookies)


def test_update_account_partial_only_changes_specified_fields():
    _run(create_account({
        "id": "u1", "name": "Original", "platform": "youtube",
        "cookies_path": None, "proxy": None, "preferred_preset": "default",
    }))
    ok = _run(update_account("u1", {"name": "Renamed"}))
    assert ok is True
    row = _run(get_account("u1"))
    assert row["name"] == "Renamed"
    assert row["preferred_preset"] == "default"   # untouched


def test_update_account_unknown_returns_false():
    assert _run(update_account("does_not_exist", {"name": "x"})) is False


def test_delete_account_regular_row_succeeds():
    _run(create_account({
        "id": "delme", "name": "x", "platform": "youtube",
        "cookies_path": None, "proxy": None, "preferred_preset": "default",
    }))
    ok = _run(delete_account("delme"))
    assert ok is True
    assert _run(get_account("delme")) is None


def test_delete_default_account_returns_false():
    """The 'default' row is the system fallback — must always exist."""
    assert _run(delete_account("default")) is False
    assert _run(get_account("default")) is not None


def test_touch_account_updates_last_used():
    _run(create_account({
        "id": "t1", "name": "x", "platform": "youtube",
        "cookies_path": None, "proxy": None, "preferred_preset": "default",
    }))
    _run(touch_account("t1"))
    row = _run(get_account("t1"))
    assert row.get("last_used_at") is not None


# ─── Account API helpers ─────────────────────────────────────────────────────

def test_api_create_new_account_rejects_unknown_preset():
    body = acc_api.AccountCreate(name="x", preferred_preset="invalid_preset")
    with pytest.raises(HTTPException) as exc:
        _run(acc_api.create_new_account(body))
    assert exc.value.status_code == 400
    assert "preset" in str(exc.value.detail).lower()


def test_api_create_new_account_happy_path():
    body = acc_api.AccountCreate(
        name="Happy Channel", preferred_preset="youtube_cuts",
    )
    out = _run(acc_api.create_new_account(body))
    assert out.name == "Happy Channel"
    assert out.id
    assert out.preferred_preset == "youtube_cuts"


def test_api_patch_unknown_account_404():
    with pytest.raises(HTTPException) as exc:
        _run(acc_api.patch_account(
            "does_not_exist", acc_api.AccountUpdate(name="x"),
        ))
    assert exc.value.status_code == 404


def test_api_patch_invalid_preset_400():
    with pytest.raises(HTTPException) as exc:
        _run(acc_api.patch_account(
            "default", acc_api.AccountUpdate(preferred_preset="bogus"),
        ))
    assert exc.value.status_code == 400


def test_api_get_single_404():
    with pytest.raises(HTTPException) as exc:
        _run(acc_api.get_single_account("no-such-id"))
    assert exc.value.status_code == 404


def test_api_delete_default_forbidden():
    with pytest.raises(HTTPException) as exc:
        _run(acc_api.remove_account("default"))
    assert exc.value.status_code == 400
    assert "default" in str(exc.value.detail).lower()


def test_api_delete_unknown_404():
    with pytest.raises(HTTPException) as exc:
        _run(acc_api.remove_account("not-here"))
    assert exc.value.status_code == 404


# ─── Publish-dispatch uses accounts ─────────────────────────────────────────

def _stub_clip():
    return {"id": "clip-1", "file_path": "clip.mp4"}


def test_publish_via_browser_account_id_loads_cookies_path(monkeypatch, tmp_path):
    # These tests cover the legacy ytb_up fork; we opt in via env
    # so monkeypatching pub_api.upload_with_cookies still applies.
    monkeypatch.setattr(pub_api, "PUBLISHER_BACKEND", "ytb_up")
    cookies = tmp_path / "ch1_cookies.json"
    cookies.write_text(json.dumps([
        {"name": "A", "value": "1", "domain": ".yt.com",
         "sameSite": "no_restriction"}
    ]))
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    _run(create_account({
        "id": "ch1", "name": "Ch 1", "platform": "youtube",
        "cookies_path": str(cookies), "proxy": "socks5://10.0.0.1:1080",
        "preferred_preset": "default",
    }))
    (tmp_path / "clip.mp4").write_bytes(b"\x00")

    class _StubReq:
        clip_id = "clip-1"; title = "t"; description = "d"; tags = []
        privacy_status = "public"; method = "browser"
        account_id = "ch1"; cookies_path = None

    seen = {}
    async def fake_upload(**kw):
        seen["cookies"] = str(kw["cookies_path"])
        seen["proxy"]   = kw["proxy"]
        return pub_api.PublishResponse(youtube_url="u", status="success", message="ok")
    monkeypatch.setattr(pub_api, "upload_with_cookies", fake_upload)

    res = _run(pub_api._publish_via_browser(_stub_clip(), _StubReq()))
    assert res.status == "success"
    assert "ch1_cookies.json" in seen["cookies"] or "ch1.json" in seen["cookies"]
    assert seen["proxy"] == "socks5://10.0.0.1:1080"


def test_publish_via_browser_account_id_unknown_404(monkeypatch, tmp_path):
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    class _StubReq:
        clip_id = "c"; title = "t"; description = ""; tags = []
        privacy_status = "public"; method = "browser"
        account_id = "no-such-acc"; cookies_path = None
    with pytest.raises(HTTPException) as exc:
        _run(pub_api._publish_via_browser(_stub_clip(), _StubReq()))
    assert exc.value.status_code == 404


def test_publish_via_browser_touches_account_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(pub_api, "PUBLISHER_BACKEND", "ytb_up")
    cookies = tmp_path / "acc_a.json"
    cookies.write_text(json.dumps([
        {"name": "A", "value": "1", "domain": ".yt.com", "sameSite": "Lax"},
    ]))
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    _run(create_account({
        "id": "a", "name": "A", "platform": "youtube",
        "cookies_path": str(cookies), "proxy": None,
        "preferred_preset": "default",
    }))
    (tmp_path / "clip.mp4").write_bytes(b"\x00")

    class _StubReq:
        clip_id = "c"; title = "t"; description = ""; tags = []
        privacy_status = "public"; method = "browser"
        account_id = "a"; cookies_path = None

    async def fake_upload(**_):
        return pub_api.PublishResponse(youtube_url="u", status="success", message="ok")
    monkeypatch.setattr(pub_api, "upload_with_cookies", fake_upload)

    _run(pub_api._publish_via_browser(_stub_clip(), _StubReq()))
    row = _run(get_account("a"))
    assert row.get("last_used_at") is not None


def test_publish_via_browser_explicit_cookies_path_overrides_account(
    monkeypatch, tmp_path
):
    """`request.cookies_path` bypasses the account lookup entirely."""
    monkeypatch.setattr(pub_api, "PUBLISHER_BACKEND", "ytb_up")
    account_cookies = tmp_path / "account.json"
    account_cookies.write_text(json.dumps([]))
    user_override = tmp_path / "override.json"
    user_override.write_text(json.dumps([
        {"name": "A", "value": "1", "domain": ".yt.com"}
    ]))
    monkeypatch.setattr(pub_api, "WORKSPACE_DIR", tmp_path)
    _run(create_account({
        "id": "ovr-acc", "name": "Ovr", "platform": "youtube",
        "cookies_path": str(account_cookies), "proxy": None,
        "preferred_preset": "default",
    }))
    (tmp_path / "clip.mp4").write_bytes(b"\x00")

    class _StubReq:
        clip_id = "c"; title = "t"; description = ""; tags = []
        privacy_status = "public"; method = "browser"
        account_id = "ovr-acc"; cookies_path = str(user_override)

    seen = {}
    async def fake_upload(**kw):
        seen["cookies"] = str(kw["cookies_path"])
        return pub_api.PublishResponse(youtube_url="u", status="success", message="ok")
    monkeypatch.setattr(pub_api, "upload_with_cookies", fake_upload)

    _run(pub_api._publish_via_browser(_stub_clip(), _StubReq()))
    assert seen["cookies"].endswith("override.json")


# ─── /api/accounts end-to-end via TestClient ─────────────────────────────────

def test_accounts_endpoints_via_test_client(tmp_path, monkeypatch):
    """Smoke test: get/create/patch/delete all round-trip via FastAPI."""
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)

    # Seed: list always has 'default' at minimum.
    r = c.get("/api/accounts")
    assert r.status_code == 200
    assert any(a["id"] == "default" for a in r.json())

    # Create + patch + delete.
    cookies = tmp_path / "creds.json"
    cookies.write_text("[]")
    payload = {
        "name": "E2E Channel",
        "preferred_preset": "films_anime",
        "cookies_path": str(cookies),
    }
    r = c.post("/api/accounts", json=payload)
    assert r.status_code == 201, r.text
    created = r.json()
    acc_id = created["id"]
    assert created["name"] == "E2E Channel"

    r = c.patch(f"/api/accounts/{acc_id}", json={"name": "E2E Channel v2"})
    assert r.status_code == 200
    assert r.json()["name"] == "E2E Channel v2"

    # Forbidden: cannot delete default.
    r = c.delete("/api/accounts/default")
    assert r.status_code == 400

    r = c.delete(f"/api/accounts/{acc_id}")
    assert r.status_code == 204

    r = c.get(f"/api/accounts/{acc_id}")
    assert r.status_code == 404
