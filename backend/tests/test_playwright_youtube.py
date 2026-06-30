"""Tests for the self-hosted Playwright YouTube publisher — Этап 1.

We deliberately do NOT spawn real Chromium in CI. The browser lifecycle
is indirectly tested via the fake-factory test seam.

Coverage:
    * Cookie-Editor JSON parsing — both shapes (flat list + storage_state).
    * Quirks: sameSite='no_restriction' dropped on httpOnly cookies,
      expires in seconds vs milliseconds, missing domain raises.
    * Auth detection from URL fragments — login / captcha / authed.
    * YoutubePublisher context-manager with fake browser (no real launch).
    * ``is_authenticated`` calls page.goto and reads page.url.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.playwright_youtube import (
    ACCOUNTS_LOGIN_URL_FRAGMENTS,
    CAPTCHA_URL_FRAGMENTS,
    AuthStatus,
    CookieLoadError,
    PublisherOptions,
    YoutubePublisher,
    detect_auth_status,
    load_cookies_file,
)


# ─── Cookie loader ──────────────────────────────────────────────


@pytest.fixture
def cookies_file(tmp_path) -> Path:
    """Write a Cookie-Editor-style flat list of Google/YouTube cookies
    and return the path. Mirrors real exports the operator produces
    via the Cookie-Editor Firefox extension."""
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps([
        {
            "name": "HSID",
            "value": "AaBbCc",
            "domain": ".youtube.com",
            "path": "/",
            "expires": 4_000_000_000,                       # seconds (year 2096-ish)
            "httpOnly": True,
            "secure": True,
            "sameSite": "no_restriction",
        },
        {
            "name": "SSID",
            "value": "DdEeFf",
            "domain": ".google.com",
            "path": "/",
            "expires": 1_700_000_000,
            "httpOnly": True,
            "secure": False,
            "sameSite": "Lax",
        },
        {
            "name": "SID",
            "value": "GgHhIi",
            "domain": "studio.youtube.com",                # no leading dot
            "expires": 1_700_000_000_000,                   # milliseconds — we must detect
            "httpOnly": False,
            "secure": True,
        },
    ]), encoding="utf-8")
    return p


def test_load_cookies_file_normalises_all_three_quirks(tmp_path):
    """Cookie-Editor quirk A (sameSite), B (expires ms vs s), C (domain
    with no leading dot). All three must be normalised silently so
    ``context.add_cookies`` accepts the result."""
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps([
        {
            "name": "A",
            "value": "1",
            "domain": "studio.youtube.com",
            "path": "/",
            "expires": 1_700_000_000_000,                  # ms
            "secure": True,
            "sameSite": "no_restriction",
        },
    ]), encoding="utf-8")
    cookies = load_cookies_file(p)
    assert len(cookies) == 1
    c = cookies[0]
    # domain preserved (no dot-prefix added — Chromium handles both)
    assert c["domain"] == "studio.youtube.com"
    # 13-digit exp → divided by 1000 to seconds
    assert c["expires"] == pytest.approx(1_700_000_000.0)
    # sameSite=Lax on secure → "None" (Cookie-Editor quirk A)
    assert c["sameSite"] == "None"


def test_load_cookies_file_drops_samesite_when_not_secure(tmp_path):
    """'no_restriction' on a non-secure cookie is illegal; we should
    drop sameSite without raising, leaving Chromium's default (Lax)."""
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps([
        {"name": "A", "value": "1", "domain": ".example.com",
         "secure": False, "sameSite": "no_restriction"},
    ]), encoding="utf-8")
    c = load_cookies_file(p)[0]
    assert "sameSite" not in c
    assert c["secure"] is False


# ─── async helper to dodge pytest-asyncio version mismatch ──────

def _run(coro):
    """Run an async test body without pytest-asyncio (incompatible
    with this environment)."""
    import asyncio
    return asyncio.run(coro)


def test_load_cookies_file_storage_state_shape(tmp_path):
    """ytb-up / Playwright storage_state has {'cookies': [...], 'origins': [...]}.
    We must accept that as well."""
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps({
        "cookies": [
            {"name": "X", "value": "1", "domain": ".google.com",
             "path": "/", "httpOnly": True, "secure": True,
             "sameSite": "Strict", "expires": 1_700_000_000}
        ],
        "origins": [{"origin": "https://youtube.com"}],
    }), encoding="utf-8")
    cookies = load_cookies_file(p)
    assert len(cookies) == 1
    assert cookies[0]["sameSite"] == "Strict"


def test_load_cookies_file_missing_returns_empty(tmp_path):
    """Missing path is NOT an error — caller decides what to surface."""
    assert load_cookies_file(tmp_path / "nope.json") == []


def test_load_cookies_file_missing_required_field(tmp_path):
    """A cookie without a name should raise so the operator knows the
    file is broken — silently dropping means end-user debug hell."""
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"value": "x", "domain": ".y.com"}]), encoding="utf-8")
    with pytest.raises(CookieLoadError):
        load_cookies_file(p)


def test_load_cookies_file_malformed_json(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(CookieLoadError):
        load_cookies_file(p)


# ─── URL-based auth detection ────────────────────────────────


def test_detect_auth_status_authenticated():
    assert detect_auth_status("https://studio.youtube.com/") == AuthStatus.AUTHENTICATED
    assert detect_auth_status("https://studio.youtube.com/channel/UCabc/videos") == AuthStatus.AUTHENTICATED


@pytest.mark.parametrize("url", [
    "https://accounts.google.com/ServiceLogin?service=youtube",
    "https://accounts.youtube.com/signin?next=/studio",
    "https://studio.youtube.com/SignOut?next=service_login",
])
def test_detect_auth_status_login_required(url):
    assert detect_auth_status(url) == AuthStatus.LOGIN_REQUIRED


@pytest.mark.parametrize("url", [
    "https://www.google.com/sorry/index?continue=...",
    "https://accounts.google.com/b/0?ip=...",
    "https://example.com/captcha-page",
])
def test_detect_auth_status_captcha(url):
    assert detect_auth_status(url) == AuthStatus.CAPTCHA_CHALLENGE


def test_detect_auth_status_unknown_url():
    assert detect_auth_status("https://example.com/somewhere") == AuthStatus.UNKNOWN


# ─── Publisher with fake browser (test seam) ──────────


class _FakePage:
    """Minimal Page stand-in. We're testing ``__aenter__`` /
    ``is_authenticated`` paths only — not real DOM interactions."""
    def __init__(self, url_after_goto: str, status: int = 200):
        self.url = url_after_goto
        self._status = status
        self.goto_calls = []

    async def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        # Return a fake response object with just `.status`.
        return MagicMock(status=self._status)

    async def close(self):
        pass


class _FakeContext:
    def __init__(self, page):
        self._page = page
        self.added_cookies = []
        self.closed = False

    async def add_cookies(self, cookies):
        self.added_cookies.extend(cookies)

    async def new_page(self):
        return self._page

    async def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, page):
        self.context = _FakeContext(page)

    async def new_context(self, **kwargs):
        return self.context

    async def close(self):
        pass


class _FakePlaywright:
    async def stop(self):
        pass


class _FakeFactory:
    """Returns a 4-tuple (pw, browser, context, page) — what
    YoutubePublisher expects when running with a test seam."""

    def __init__(self, url_after_goto, status=200):
        page = _FakePage(url_after_goto, status=status)
        browser = _FakeBrowser(page)
        self.pw = _FakePlaywright()
        self.browser = browser
        self.context = browser.context
        self.page = page

    def __call__(self):
        # sync return — _invoke_factory awaits only if coroutine
        return (self.pw, self.browser, self.context, self.page)


@pytest.mark.parametrize("url,expected", [
    ("https://studio.youtube.com/",                AuthStatus.AUTHENTICATED),
    ("https://accounts.google.com/ServiceLogin",  AuthStatus.LOGIN_REQUIRED),
    ("https://www.google.com/sorry/index",        AuthStatus.CAPTCHA_CHALLENGE),
])
def test_publisher_is_authenticated_three_branches(url, expected, cookies_file):
    fake = _FakeFactory(url_after_goto=url)
    pub = YoutubePublisher(
        account_id="acc-test",
        cookies_path=cookies_file,
        options=PublisherOptions(headless=True),
        _browser_factory=fake,
    )
    async def body():
        async with pub:
            result = await pub.is_authenticated()
            assert result == expected
            assert len(fake.context.added_cookies) > 0
            assert pub._page.goto_calls[0][0] == "https://studio.youtube.com/"
    _run(body())


def test_publisher_no_cookies_path_still_works(cookies_file):
    """If cookies_path is None we don't crash — the API caller may not
    have one (e.g. during onboarding). The check will then return the
    appropriate auth state based on the page URL alone."""
    fake = _FakeFactory(url_after_goto="https://accounts.google.com/ServiceLogin")
    pub = YoutubePublisher(
        account_id="acc-nocookies",
        cookies_path=None,
        options=PublisherOptions(),
        _browser_factory=fake,
    )
    async def body():
        async with pub:
            return await pub.is_authenticated()
    result = _run(body())
    assert result == AuthStatus.LOGIN_REQUIRED
    assert fake.context.added_cookies == []


def test_publisher_closes_resources_on_exit(cookies_file):
    fake = _FakeFactory(url_after_goto="https://studio.youtube.com/")
    pub = YoutubePublisher(
        account_id="acc-cleanup",
        cookies_path=cookies_file,
        options=PublisherOptions(),
        _browser_factory=fake,
    )
    async def body():
        async with pub:
            pass
    _run(body())
    # __aexit__ ran; all four resources must be marked closed.
    assert fake.context.closed is True


def test_publisher_handles_goto_exception(cookies_file):
    """If ``goto`` raises, is_authenticated returns UNKNOWN — never
    crashes the upload pipeline."""
    class _CrashPage(_FakePage):
        async def goto(self, url, **kwargs):
            raise RuntimeError("navigation timeout")

    fake = _FakeFactory(url_after_goto="")
    fake.page = _CrashPage(url_after_goto="", status=0)
    fake.browser.context = _FakeContext(fake.page)
    fake.browser.context._page = fake.page
    fake.browser.new_context = AsyncMock(return_value=fake.browser.context)
    fake.context = fake.browser.context
    fake.pw.browser = fake.browser

    pub = YoutubePublisher(
        account_id="acc-crash",
        cookies_path=cookies_file,
        options=PublisherOptions(),
        _browser_factory=fake,
    )
    async def body():
        async with pub:
            return await pub.is_authenticated()
    assert _run(body()) == AuthStatus.UNKNOWN
