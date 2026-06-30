"""Self-hosted Playwright YouTube Studio publisher — foundation module.

This is the long-term replacement for ``youtube_browser_publisher.py``
(which today thinly wraps ``ytb-up``). The legacy wrapper is kept around
behind the ``CLIPFORGE_PUBLISHER_BACKEND=ytb_up`` env switch while we
migrate.

What's in here (Этап 1 — foundation):

    * :class:`YoutubePublisher` — async context manager that opens a
      Playwright browser (Chromium / Firefox / Webkit), loads cookies
      into the BrowserContext, and exposes ``is_authenticated()``.
    * :func:`load_cookies_file` — read Cookie-Editor JSON, normalise to
      Playwright's `add_cookies` schema, fix the well-known
      ``sameSite: 'no_restriction'`` quirk so we don't crash on
      ytb-up-style exports.
    * :func:`detect_auth_status` — given the URL we landed on after
      opening studio.youtube.com, classify as
      ``authenticated | login_required | captcha_challenge | unknown``.
      We don't use screen-scraping of YouTube's DOM here; we judge
      purely from the URL pattern because Google routes "not signed in"
      to ``accounts.google.com/ServiceLogin`` and "captcha / bot
      challenge" to its ``/sorry/`` challenge page. Both are stable
      signals.

What's NOT in here yet (Этап 2-3):

    * the actual upload form interaction (file picker, next-next-publish)
    * scheduled vs immediate publishing
    * per-account persistent Firefox profile directory
    * rate-limits, retries, captcha recovery

Adding them later is additive — the public API ``YoutubePublisher``
and ``__aenter__/__aexit__`` contract stay the same.

Test seam:
    ``YoutubePublisher.__init__`` accepts an optional ``_browser_factory``
    callable. When the test passes a fake factory it never reaches the
    real Playwright; CI never spawns Chromium.
"""
from __future__ import annotations

import asyncio
import enum
import json
import logging
import os
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

logger = logging.getLogger(__name__)


# ─── Domain constants ────────────────────────────────────────────────────────

# YouTube Studio routes the operator to various Google-owned URLs
# depending on session state. Both URLs are stable across years.
YOUTUBE_STUDIO_URL = "https://studio.youtube.com/"
ACCOUNTS_LOGIN_URL_FRAGMENTS = (
    "accounts.google.com/ServiceLogin",
    "accounts.google.com/v3/signin",
    "accounts.youtube.com/signin",
    "SignOut",                # /SignOut is what we see on cookie-expiry
)
CAPTCHA_URL_FRAGMENTS = (
    "/sorry/",                # Google "unusual traffic" page
    "accounts.google.com/b/",
    "captcha",
)


class AuthStatus(str, enum.Enum):
    AUTHENTICATED = "authenticated"
    LOGIN_REQUIRED = "login_required"
    CAPTCHA_CHALLENGE = "captcha_challenge"
    UNKNOWN = "unknown"


# ─── Cookie loader ──────────────────────────────────────────────────────────


class CookieLoadError(ValueError):
    """Raised when cookies.json is structurally unusable."""


def _normalise_one_cookie(raw: dict) -> dict:
    """Adapt a single Cookie-Editor / ytb-up cookie entry into the
    shape Playwright's ``context.add_cookies`` accepts.

    Quirks handled:
        • ``sameSite: "no_restriction"`` → dropped entirely (Playwright
          errors with: 'value "None" is none of "Strict", "Lax", "None"').
        • Missing required fields (``name`` / ``value`` / ``domain``) →
          raise CookieLoadError.
        • Unix timestamps in seconds *or* milliseconds → normalised.
    """
    if not isinstance(raw, dict):
        raise CookieLoadError(f"cookie entry must be a dict, got {type(raw).__name__}")
    for required in ("name", "value"):
        if not raw.get(required):
            raise CookieLoadError(f"cookie missing required field: {required!r}")

    out: dict = {
        "name":     raw["name"],
        "value":    raw["value"],
        "domain":   raw.get("domain") or raw.get("host"),
        "path":     raw.get("path") or "/",
    }
    if not out["domain"]:
        raise CookieLoadError(f"cookie {raw['name']!r} has no domain")

    # Boolean flags — default false if absent. Cookie-Editor uses true/false.
    out["httpOnly"] = bool(raw.get("httpOnly", False))
    out["secure"]   = bool(raw.get("secure", False))

    # sameSite: only Strict | Lax | None are valid; mapping
    # "no_restriction" (Cookie-Editor's spelling) → drop the field.
    ss = raw.get("sameSite")
    if ss in ("Strict", "Lax"):
        out["sameSite"] = ss
    elif ss in ("None", "no_restriction"):
        # Playwright accepts "None" only when secure=true (per spec),
        # so we drop sameSite altogether — Chromium falls back to the
        # browser default which is fine for a session login.
        if out["secure"]:
            out["sameSite"] = "None"
    # else: omit the field; Chromium treats default-Unset sameSite as Lax.

    # Expiry. Both Cookie-Editor (Unix seconds) and ytb-up's storage_state
    # format (Unix seconds) use seconds; we still defensively detect
    # milliseconds ("13-digit" timestamps).
    if raw.get("expires") is not None and raw["expires"] >= 0:
        exp = float(raw["expires"])
        if exp > 1e12:                       # > year ~33658 in seconds
            exp /= 1000.0                    # was milliseconds
        out["expires"] = exp

    return out


def load_cookies_file(cookies_path: Path) -> List[dict]:
    """Read a Cookie-Editor export and return a list of Playwright-shaped
    cookie dicts ready for ``context.add_cookies``.

    Returns [] rather than raising for a missing file — the caller
    (Publisher) is responsible for surfacing the "no cookies" error to
    the user.

    Raises :class:`CookieLoadError` only when the file *exists* but is
    structurally broken, because silently shipping nothing cookies in
    that case would be a confusing failure mode.
    """
    cookies_path = Path(cookies_path)
    if not cookies_path.exists():
        return []
    try:
        raw = json.loads(cookies_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CookieLoadError(f"{cookies_path.name} is not valid JSON: {e}") from e

    cookies: Iterable[dict]
    # Two on-disk shapes exist:
    #   1. flat list (Cookie-Editor "Export as JSON"): [{"name":..., ...}, ...]
    #   2. ytb-up storage_state shape: {"cookies": [...], "origins": [...]}
    if isinstance(raw, list):
        cookies = raw
    elif isinstance(raw, dict) and isinstance(raw.get("cookies"), list):
        cookies = raw["cookies"]
    else:
        raise CookieLoadError(
            f"{cookies_path.name} has unexpected shape - expected a "
            "list of cookie dicts or {'cookies': [...]} (storage_state)"
        )

    return [_normalise_one_cookie(c) for c in cookies]


# ─── Auth state from a URL ──────────────────────────────────────────────────


def detect_auth_status(url: str) -> AuthStatus:
    """Classify the post-redirect URL into AuthStatus.

    We don't try to parse YouTube Studio's DOM — the URLs themselves
    are reliable signals because every Google login / captcha path is
    routed through ``accounts.google.com`` or ``/sorry/`` first.
    """
    if not url:
        return AuthStatus.UNKNOWN
    lower = url.lower()
    for frag in (f.lower() for f in CAPTCHA_URL_FRAGMENTS):
        if frag in lower:
            return AuthStatus.CAPTCHA_CHALLENGE
    for frag in (f.lower() for f in ACCOUNTS_LOGIN_URL_FRAGMENTS):
        if frag in lower:
            return AuthStatus.LOGIN_REQUIRED
    if "studio.youtube.com" in lower and "signout" not in lower:
        return AuthStatus.AUTHENTICATED
    return AuthStatus.UNKNOWN


# ─── Publisher ──────────────────────────────────────────────────────────────


# These env flips let ops tune the runtime without recompiling.
_DEFAULT_BROWSER = "chromium"
_DEFAULT_LOCALE = "en-US"
_DEFAULT_HEADLESS = True

# Realistic viewport set — headless Chromium with default 1280×720
# trips Google's "is this automated?" heuristics. Pick a number from
# real laptops' DPR-tweaked resolutions.
_USER_AGENTS = (
    # latest Chrome stable
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    # fallback Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
    "Gecko/20100101 Firefox/131.0",
)


@dataclass(frozen=True)
class PublisherOptions:
    """Operator-facing knobs for ``YoutubePublisher``.

    Notes:
        * ``browser`` is one of {"chromium", "firefox", "webkit"} —
          match the binary name Playwright launches.
        * ``headless`` is True by default for production. Local dev
          can flip it via env ``CLIPFORGE_PUBLISHER_HEADLESS=0``.
        * ``user_agent`` overrides the OS-default UA. Pick a stable
          Chrome UA string and stick with it — Google tracks UA drift.
        * ``user_data_dir`` — when None (default) we generate a fresh
          temporary directory per session, so each launch starts with
          a completely empty Chromium profile. Set to a real path if
          you want to reuse cookies + cache between runs (NOT
          recommended on Windows — Windows often shares the user's
          actual Chrome profile when no override is given, which can
          leak a personal login session into the playwright browser).
    """
    browser: str = _DEFAULT_BROWSER
    locale: str = _DEFAULT_LOCALE
    timezone_id: str = "UTC"
    headless: bool = True
    user_agent: str = _USER_AGENTS[0]
    proxy: Optional[str] = None      # "socks5://..." or "http://..." or None
    user_data_dir: Optional[str] = None  # None = fresh per-session profile


def _default_options() -> PublisherOptions:
    """Read env on each call so the operator can flip headless/proxy
    without restarting the whole backend."""
    headless_env = os.environ.get("CLIPFORGE_PUBLISHER_HEADLESS", "1")
    headless = headless_env not in ("0", "false", "no")
    return PublisherOptions(
        headless=headless,
        user_agent=os.environ.get("CLIPFORGE_PUBLISHER_UA", _USER_AGENTS[0]),
        proxy=os.environ.get("CLIPFORGE_PUBLISHER_PROXY") or None,
    )


# Test seam: a factory that returns ``(browser_type, playwright_instance)``
# tuples. ``None`` means "spawn a real Playwright". Tests inject a
# stub factory that returns a fake browser with a fake page.
BrowserFactory = Callable[[], Any]


class YoutubePublisher:
    """Async context manager that opens a browser session for one
    account. Use::

        async with YoutubePublisher(account_id, cookies_path=...) as pub:
            auth = await pub.is_authenticated()
            ...

    Closing the context tears down the browser. After the block exits
    you cannot reuse the publisher — open a new one for the next clip.
    """

    def __init__(
        self,
        account_id: str,
        cookies_path: Optional[Path] = None,
        *,
        options: Optional[PublisherOptions] = None,
        _browser_factory: Optional[BrowserFactory] = None,
    ) -> None:
        self.account_id = account_id
        self.cookies_path = Path(cookies_path) if cookies_path else None
        self.options = options or _default_options()
        self._browser_factory = _browser_factory
        # Filled in __aenter__ — left None before that.
        self._pw = None        # playwright instance
        self._browser = None   # Browser
        self._context = None   # BrowserContext (cookies applied HERE)
        self._page = None      # Page

    # ── context-manager protocol ────────────────────────────────────────
    async def __aenter__(self) -> "YoutubePublisher":
        await self._open()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._close()

    # ── backends for tests / real ───────────────────────────────────────
    def _factory(self) -> Any:
        """Resolve the browser factory, falling back to the real
        Playwright entry point when no test seam is provided."""
        if self._browser_factory is not None:
            return self._browser_factory()
        # Lazy import so unit tests don't pull playwright-launch deps.
        from playwright.async_api import async_playwright
        # async_playwright() is an async generator; in __aenter__ we
        # call `await _factory()` via __aenter__ — see _open.
        raise RuntimeError(
            "_factory must be awaited inside an async context"
        )

    # ── internal open/close ────────────────────────────────────────────
    async def _open(self) -> None:
        if self._browser_factory is not None:
            # Test-mode: factory returns whatever it likes; we accept
            # anything that quacks like (pw, browser, context, page).
            handle = await self._invoke_factory()
            self._pw, self._browser, self._context, self._page = handle
        else:
            # Real mode. Use Playwright-async inside same coroutine.
            from playwright.async_api import async_playwright
            import tempfile

            self._pw = await async_playwright().start()
            launcher = getattr(self._pw, self.options.browser, None)
            if launcher is None:
                raise RuntimeError(f"unknown browser: {self.options.browser}")

            # Per-session isolated Chrome profile. Chromium triples down
            # on isolation when we use ``launch_persistent_context`` —
            # the persistent context IS the BrowserContext AND the
            # Browser, and it owns the per-session ``--user-data-dir``
            # directory. We get a clean profile every run; the user's
            # real Chrome state cannot leak in because Playwright refuses
            # ``--user-data-dir=`` as a command-line arg on plain
            # ``launch()`` ("Pass user_data_dir parameter to
            # 'browser_type.launch_persistent_context' instead of
            # specifying '--user-data-dir' argument").
            profile_dir = self.options.user_data_dir or tempfile.mkdtemp(
                prefix=f"clipforge-publisher-{os.getpid()}-"
            )

            common_kwargs = {
                "headless": self.options.headless,
                "locale":   self.options.locale,
                "timezone_id": self.options.timezone_id,
                "viewport": {"width": 1280, "height": 800},
                "user_agent": self.options.user_agent,
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if self.options.proxy:
                common_kwargs["proxy"] = {"server": self.options.proxy}

            # launch_persistent_context returns a BrowserContext directly
            # (NOT a Browser). We expose ``self._context`` and store the
            # same instance at ``self._browser`` so legacy ``_close()``
            # checks (which closed browser first then context) still
            # close something. Closing the persistent context closes
            # the underlying Browser automatically.
            self._context = await launcher.launch_persistent_context(
                user_data_dir=profile_dir,
                **common_kwargs,
            )
            self._browser = self._context
            self._page = await self._context.new_page()

        # Cookie loading happens AFTER context exists, regardless of
        # real-vs-test mode. Tests verify that ``cookies_path`` is
        # plumbed through to ``context.add_cookies``; the real path
        # also benefits from 'load' being a single concern.
        if self.cookies_path:
            cookies = load_cookies_file(self.cookies_path)
            if cookies:
                await self._context.add_cookies(cookies)

    async def _invoke_factory(self):
        """Translate whatever the test factory returns into the
        (pw, browser, context, page) 4-tuple we use internally."""
        rv = self._browser_factory()
        if asyncio.iscoroutine(rv):
            rv = await rv
        # Two shapes accepted:
        #   1. 4-tuple: (pw, browser, context, page)
        #   2. single object with `.pw, .browser, .context, .page`
        if isinstance(rv, tuple) and len(rv) == 4:
            return rv
        return (getattr(rv, "pw"), getattr(rv, "browser"),
                getattr(rv, "context"), getattr(rv, "page"))

    async def _close(self) -> None:
        # Order matters: page → context → browser → playwright.
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                pass
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass

    # ── public API ─────────────────────────────────────────────────────

    async def is_authenticated(self) -> AuthStatus:
        """Open studio.youtube.com and report whether we're logged in.

        Side-effect: drives the navigation through whatever Google
        auth/cookies/captcha redirects, so the first call is also a
        cheap "do my cookies still work?" smoke.
        """
        if self._page is None:
            raise RuntimeError("call is_authenticated inside 'async with'")
        try:
            response = await self._page.goto(
                YOUTUBE_STUDIO_URL,
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            final_url = self._page.url
            # Empty URL → goto failed. response may carry status info.
            logger.info(
                f"[YT-Playwright] auth probe for "
                f"account={self.account_id!r} → status="
                f"{(response.status if response else 'no-response')} "
                f"final={final_url[:120]!r}"
            )
            return detect_auth_status(final_url)
        except Exception as e:
            logger.warning(
                f"[YT-Playwright] auth probe crashed for "
                f"account={self.account_id!r}: {e}"
            )
            return AuthStatus.UNKNOWN


# Convenience factory for callers that don't care about the full
# options object — pass cookie_path + account_id, get a publisher.
def build_publisher(
    account_id: str,
    cookies_path: Optional[Path],
    **opts_extra,
) -> YoutubePublisher:
    return YoutubePublisher(
        account_id, cookies_path,
        options=PublisherOptions(**opts_extra) if opts_extra else None,
    )


__all__ = [
    "AuthStatus",
    "CookieLoadError",
    "PublisherOptions",
    "YoutubePublisher",
    "build_publisher",
    "detect_auth_status",
    "load_cookies_file",
]
