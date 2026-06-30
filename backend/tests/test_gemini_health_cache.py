"""Tests for GeminiDirector.check_health() health-cache behaviour.

The free-tier Gemini 3.5 Flash has ≈20 RPD, so a dedicated pre-flight
request per video halves the daily budget. We memoize a successful
pre-flight for `ttl` seconds — verify the cache works, expires, and is
invalidated by terminal failures.
"""
import time
import pytest
from unittest.mock import MagicMock, patch

from backend.services.gemini_director import GeminiDirector


@pytest.fixture(autouse=True)
def _isolate_class_state():
    """Reset the class-level health cache before each test so they don't
    leak state. `_ttl_sec` always reflects whatever env-var was set at
    import time, which is fine for these unit-tests."""
    GeminiDirector._health_cache["ok_at_monotonic"] = None
    yield


@pytest.fixture
def _configured_gemini():
    """Make check_health() believe Gemini is configured (keys non-empty)."""
    with patch.multiple(
        "backend.services.gemini_director",
        GEMINI_API_KEY="test-key",
        GEMINI_PROXY="http://test-proxy:3128",
    ):
        yield


def _fake_response(status_code: int = 200, text: str = '{"candidates":[]}'):
    """Build a context-manager-friendly httpx.Response substitute."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = MagicMock(side_effect=None)
    return resp


def test_check_health_first_call_hits_api(_configured_gemini):
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc:
        client = MagicMock()
        client.post.return_value = _fake_response(200)
        bc.return_value.__enter__.return_value = client
        # Force TTL=0 so cache is bypassed regardless.
        old = GeminiDirector._health_cache["ttl_sec"]
        GeminiDirector._health_cache["ttl_sec"] = 0
        try:
            assert director.check_health() is True
        finally:
            GeminiDirector._health_cache["ttl_sec"] = old
    assert client.post.call_count == 1


def test_check_health_cached_within_ttl_skips_api(_configured_gemini):
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc:
        client = MagicMock()
        client.post.return_value = _fake_response(200)
        bc.return_value.__enter__.return_value = client
        # Prime the cache via a real call first.
        old = GeminiDirector._health_cache["ttl_sec"]
        GeminiDirector._health_cache["ttl_sec"] = 0
        director.check_health()  # populates the cache
        # Now bump TTL to a huge value so the next call must hit the cache.
        GeminiDirector._health_cache["ttl_sec"] = 600
        try:
            ok1 = director.check_health()
            ok2 = director.check_health()
        finally:
            GeminiDirector._health_cache["ttl_sec"] = old
    # Only the prime call should have triggered an HTTP request.
    assert client.post.call_count == 1, (
        f"cache miss detected, calls={client.post.call_count}"
    )
    assert ok1 is True and ok2 is True


def test_check_health_cache_expires_after_ttl(_configured_gemini):
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc:
        client = MagicMock()
        client.post.return_value = _fake_response(200)
        bc.return_value.__enter__.return_value = client
        old_ttl = GeminiDirector._health_cache["ttl_sec"]
        try:
            # Prime with TTL=0 (no cache) — first POST.
            GeminiDirector._health_cache["ttl_sec"] = 0
            director.check_health()
            assert client.post.call_count == 1

            # Set a tiny TTL, then sleep past it.
            GeminiDirector._health_cache["ttl_sec"] = 0.05
            time.sleep(0.1)
            director.check_health()
        finally:
            GeminiDirector._health_cache["ttl_sec"] = old_ttl
    assert client.post.call_count == 2, "expired cache should re-probe"


def test_check_health_force_bypasses_cache(_configured_gemini):
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc:
        client = MagicMock()
        client.post.return_value = _fake_response(200)
        bc.return_value.__enter__.return_value = client
        old_ttl = GeminiDirector._health_cache["ttl_sec"]
        try:
            GeminiDirector._health_cache["ttl_sec"] = 0
            director.check_health()
            # Set huge TTL, then force=True — must re-issue the request.
            GeminiDirector._health_cache["ttl_sec"] = 600
            assert director.check_health(force=True) is True
        finally:
            GeminiDirector._health_cache["ttl_sec"] = old_ttl
    assert client.post.call_count == 2


def test_check_health_terminal_failure_invalidates_cache(_configured_gemini):
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc:
        client = MagicMock()
        # auth/region error — 403
        client.post.return_value = _fake_response(403, "Permission denied")
        bc.return_value.__enter__.return_value = client
        assert director.check_health() is False
    assert GeminiDirector._health_cache["ok_at_monotonic"] is None


def test_check_health_transient_failure_does_not_cache(_configured_gemini):
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc, \
         patch("backend.services.gemini_director._after_attempt_delay", return_value=0):
        client = MagicMock()
        # 503 transient — we RETRY (don't cache), so the timestamp stays None.
        client.post.return_value = _fake_response(503, "high demand")
        bc.return_value.__enter__.return_value = client
        assert director.check_health() is False
    assert GeminiDirector._health_cache["ok_at_monotonic"] is None


def test_invalidate_health_cache_resets_timestamp():
    GeminiDirector._health_cache["ok_at_monotonic"] = time.monotonic()
    assert GeminiDirector._health_cache["ok_at_monotonic"] is not None
    GeminiDirector().invalidate_health_cache()
    assert GeminiDirector._health_cache["ok_at_monotonic"] is None


def test_check_health_transient_failure_does_not_cache():
    director = GeminiDirector()
    with patch("backend.services.gemini_director._build_client") as bc, \
         patch("backend.services.gemini_director._after_attempt_delay", return_value=0):
        client = MagicMock()
        # 503 transient — we RETRY (don't cache), so the timestamp stays None.
        client.post.return_value = _fake_response(503, "high demand")
        bc.return_value.__enter__.return_value = client
        assert director.check_health() is False
    assert GeminiDirector._health_cache["ok_at_monotonic"] is None


def test_invalidate_health_cache_resets_timestamp():
    GeminiDirector._health_cache["ok_at_monotonic"] = time.monotonic()
    assert GeminiDirector._health_cache["ok_at_monotonic"] is not None
    GeminiDirector().invalidate_health_cache()
    assert GeminiDirector._health_cache["ok_at_monotonic"] is None
