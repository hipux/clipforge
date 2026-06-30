"""YouTube upload via `ytb-up` browser automation.

Why this exists:
    The official YouTube Data API flags automation and requires paid Google
    Workspace for >1.6k credits. For a content clipper who wants to look like
    a real human uploader, headless Playwright + channel cookies is the only
    practical path.

This module is a THIN wrapper — it does not reimplement selectors. All UI
knowledge stays inside `ytb_up.youtube`. We:
    1. Translate cookie files into a Playwright `storage_state`,
    2. Run ytb-up's `YoutubeUpload.upload(...)` in a subprocess-thread,
    3. Surface a clean `PublishResult` for the API layer.

Test isolation:
    `upload_with_cookies()` is the single entry point. Tests inject a
    `_run_youtube_upload` fake so we never spawn a real browser in CI.

Cookie JSON quirks (from ytb-up docs):
    https://github.com/microsoft/playwright/issues/12616
    Manually rewrite `no_restriction` -> `sameSite: None` in your cookies
    file before saving. We do this automatically when the file is loaded.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublishResult:
    """Slim shape returned to the API layer.

    `youtube_url` is None when the run finished but the channel UI hid the
    URL — that's still a "success" (it DID upload). The caller can refresh
    YouTube Studio to confirm.
    """
    status: str          # 'success' | 'failed' | 'skipped'
    message: str
    youtube_url: Optional[str] = None


def _cookies_to_storage_state(cookies_path: Path) -> dict:
    """Convert a cookie-export JSON file into Playwright `storage_state`.

    `ytb-up` accepts a raw cookie.json exported from Cookie-Editor. We:
        - normalise the dict so `cookies` is a list,
        - rewrite `sameSite: "no_restriction"` -> `"None"` (Playwright's enum
          value is `None` without quotes; the raw string breaks deserialiser).
    """
    raw = json.loads(cookies_path.read_text(encoding="utf-8"))
    cookies = raw if isinstance(raw, list) else raw.get("cookies", [])
    fixed = []
    for c in cookies:
        c2 = dict(c)
        ss = c2.pop("sameSite", None)
        if ss == "no_restriction":
            c2["sameSite"] = "None"
        elif ss in ("None", "Lax", "Strict"):
            c2["sameSite"] = ss
        # else: drop it; Playwright tolerates absent sameSite.
        fixed.append(c2)
    return {"cookies": fixed, "origins": raw.get("origins", []) if isinstance(raw, dict) else []}


def _resolve_youtube_upload_outcome(
    uploaded: bool, video_url: Optional[str]
) -> PublishResult:
    if not uploaded:
        return PublishResult(status="failed",
                             message="YouTube Studio UI did not confirm upload")
    return PublishResult(status="success",
                         message="Uploaded",
                         youtube_url=video_url)


async def upload_with_cookies(
    file_path: Path,
    title: str,
    description: str,
    tags: list,
    cookies_path: Path,
    profile_dir: Optional[Path] = None,
    proxy: Optional[str] = None,
    headline_path: Optional[Path] = None,
    _driver: Optional[callable] = None,
) -> PublishResult:
    """Upload a clip via Playwright + cookies.

    Arguments reflect what `ytb_up.youtube.YoutubeUpload` accepts, plus our
    own `proxy`/`headline_path` caller-side conveniences. `_driver` is the
    test seam — when given, we call it instead of opening Playwright. The
    default `_real_browser_upload()` lives below.
    """
    if not cookies_path.exists():
        return PublishResult(status="failed",
                             message=f"cookies file missing: {cookies_path}")
    if not file_path.exists():
        return PublishResult(status="failed",
                             message=f"clip file missing: {file_path}")
    # Sanity check storage_state conversion even when faking, so test path
    # exercises the same code real callers hit.
    storage_state = _cookies_to_storage_state(cookies_path)
    if not storage_state["cookies"]:
        return PublishResult(status="failed",
                             message="no usable cookies in file (login again)")

    driver = _driver or _real_browser_upload
    # Tag the call so log lines can be filtered by account in #5.
    logger.info(f"[YT-Browser] upload start: {file_path.name!r}, "
                f"title={title[:40]!r}, proxy={'on' if proxy else 'off'}")
    try:
        outcome = await asyncio.to_thread(
            driver,
            file_path=file_path,
            title=title,
            description=description,
            tags=tags,
            storage_state=storage_state,
            profile_dir=profile_dir,
            proxy=proxy,
            headline_path=headline_path,
        )
    except Exception as e:
        logger.exception(f"[YT-Browser] upload crashed: {e}")
        return PublishResult(status="failed", message=f"runtime error: {e!s}")

    uploaded, url = outcome
    return _resolve_youtube_upload_outcome(uploaded, url)


def _real_browser_upload(
    file_path: Path,
    title: str,
    description: str,
    tags: list,
    storage_state: dict,
    profile_dir: Optional[Path],
    proxy: Optional[str],
    headline_path: Optional[Path],
) -> Tuple[bool, Optional[str]]:
    """Synchronous Playwright upload. Runs in `asyncio.to_thread`.

    Implementation note: `ytb-up` ships an *async* `YoutubeUpload.upload()`
    but also has a sync `set_channel_language_english()` call we want first
    so CSS selectors hit the English version of YouTube Studio. To keep the
    code path simple (no async -> sync bridge inside our function), we
    import lazily here and run the whole Playwright flow inside the thread.
    """
    import ytb_up.youtube as yt  # type: ignore
    import datetime as dt

    profile_dir = profile_dir or Path("~/.cache/clipforge/youtube-profile").expanduser()
    profile_dir.mkdir(parents=True, exist_ok=True)
    cookies_file = profile_dir / "cookies.json"
    cookies_file.write_text(json.dumps(storage_state), encoding="utf-8")

    upload = yt.YoutubeUpload(
        root_profile_directory=str(profile_dir),
        proxy_option=proxy or "",
        timeout=3,
        watcheveryuploadstep=False,
        debug=False,
        CHANNEL_COOKIES=str(cookies_file),
    )
    # Sync-language flip before async upload (sync helper).
    try:
        if hasattr(yt, 'set_channel_language_english'):
            upload.set_channel_language_english()
    except Exception as e:
        logger.debug(f"[YT-Browser] language pre-set skipped: {e}")

    publish_date = dt.datetime.combine(
        dt.date.today(), dt.time(hour=10, minute=15)
    )
    return upload.upload(
        videopath=str(file_path),
        title=title,
        description=description,
        thumbnail=str(headline_path) if headline_path else "",
        publish_date=publish_date,
        tags=tags or [],
    )


# Re-export so other modules don't have to know about ytb_up internals.
__all__ = ["PublishResult", "upload_with_cookies"]
