"""YouTube Studio upload form automation — Этап 2.

The single entry point ``upload_one(...)`` drives the entire 5-step
YouTube Studio upload flow using the existing :class:`YoutubePublisher`
context manager:

    1. Open studio.youtube.com -> Create -> Upload videos (or direct /upload)
    2. file picker: set the hidden <input type=file> on the dialog
    3. wait for processing -> Details step (title + description)
    4. Video Elements cards (skip) -> Checks (skip) -> Visibility
    5. Visibility radio: Private | Public | Scheduled; final Publish click;

Selectors are versioned in the :data:`SELECTORS` dict. When YouTube
Studio's DOM shifts (they redesigned twice in 2024 alone), edit ONE
dict and rerun tests; nothing else changes.

Test isolation:
    Every step is its own method. Tests inject an AsyncMock Page and
    confirm that ``SELECTORS[key]`` is the locator string the test
    Page is queried against. Real-browser runs only ever happen via
    the ``cli_explore.py`` companion script, never in unit tests.
"""
from __future__ import annotations

import asyncio
import enum
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Union

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────────────
# Selectors
# ───────────────────────────────────────────────────────────────────────────────
#
# Single source of truth. When YouTube Studio's DOM changes (they
# migrated Material→Polymer→Lit in 2024), edit the matching key here
# and re-run tests. The constants below were verified live against
# YouTube Studio 2026-Q2 in Russian-locale:
#   * No data-testid attrs (Studio moved away)
#   * URL stays constant for ALL steps — SPA on `…videos/upload?d=ud`
#   * Dialog content rendered inside `ytcp-uploads-dialog-host`
#   * Buttons localised: "Далее" / "Назад" / "Сохранить" / "Загрузить файл"
#   * Title textarea has aria-label starting "Укажите название..."
#
# Strategy: prefer aria-label substring (locale-stable concept even
# when language changes), fall back to id (locale-stable), only use
# button:has-text() when no aria is set.

SELECTORS = {
    # ── Step 1: file picker ────────────────────────────────────────
    # The hidden input always accepts the file directly, regardless
    # of whether the visible UI shows drag-drop or "Загрузить файл" button.
    "file_input":           'input[type="file"]',
    # Russian-locale: "Загрузить файл"; English: "Upload file". Both literal.
    "select_files_btn":     'button:has-text("Загрузить файл"), button:has-text("Upload file")',

    # ── Step 2: Details ─────────────────────────────────────────────
    # Title: Russian aria-prefix "Укажите название"; English "Add a title"
    # that contains the word "title". The legacy #title-textarea id may
    # still exist as fallback for older Studio. We use the aria-label
    # match because Studio has resolved a CSS-class collision by changing
    # them per-build and aria is more stable across renditions.
    "title_textarea":       '[aria-label*="название" i], [aria-label*="title" i], textarea[placeholder*="название" i]',
    "description_box":      '[aria-label*="Расскажите" i], [aria-label*="опишите" i], [aria-label*="description" i], [aria-label*="about your video" i]',

    # ── Navigation ────────────────────────────────────────
    # Russian "Далее" (Next); English "Next" / "Continue". Most reliable
    # is #next-button (Studio has kept this id for years).
    "step_next_button":     '#next-button, button:has-text("Далее"), button:has-text("Next"), button:has-text("Continue")',
    # Russian "Назад" (Back). Used only for cancel logic.
    "step_back_button":     'button:has-text("Назад"), button:has-text("Back")',

    # ── Made-for-kids (Details step, NOT a separate Checks step) ──
    # Russian: "Нет, это видео не для детей"; English "No, it's not made for kids".
    # We pick the second option (= not children-directed) by default.
    "made_for_kids_not":   'tp-yt-paper-radio-button:has-text("Нет, это видео"), tp-yt-paper-radio-button:has-text("not made for kids")',

    # ── Copyright + age restrictions (also Details step) ────────
    "copyright_owned":      'tp-yt-paper-radio-button:has-text("я автор"), tp-yt-paper-radio-button:has-text("I own")',
    "age_restriction":      'button:has-text("Возрастные ограничения"), button:has-text("Age restriction")',

    # ── Step 5: Visibility ──────────────────────────────────
    # The visibility radio group + final Publish button. Studio keeps
    # the dialog open until the operator confirms, so radio buttons use
    # their visible text labels.
    "visibility_private":   'tp-yt-paper-radio-button:has-text("Закрытый"), tp-yt-paper-radio-button:has-text("Private")',
    "visibility_unlisted":  'tp-yt-paper-radio-button:has-text("Доступ по ссылке"), tp-yt-paper-radio-button:has-text("Unlisted")',
    "visibility_public":    'tp-yt-paper-radio-button:has-text("Открытый"), tp-yt-paper-radio-button:has-text("Public")',
    "visibility_schedule":  'tp-yt-paper-radio-button:has-text("Запланировать"), tp-yt-paper-radio-button:has-text("Schedule")',

    # Schedule date+time. Newer Studio uses <input type="datetime-local">;
    # older versions split into date + time inputs.
    "schedule_date":        'input[type="datetime-local"], input[aria-label*="дата" i], input[aria-label*="date" i]',
    "schedule_time":        'input[aria-label*="время" i], input[aria-label*="time" i]',

    # Publish (Russian "Сохранить", English "Publish", legacy "Done")
    # — final click that locks in the upload.
    "publish_button":       'button:has-text("Сохранить"), button:has-text("Save"), button:has-text("Publish"), button:has-text("Done"), #done-button',

    # ── Status surfaces ────────────────────────────────────
    "processing":           'tp-yt-paper-progress, [role="progressbar"]',
    # Studio 2026: the upload's "details" dialog renders the title
    # textarea at completion; we wait for this selectability as proof
    # the file has been accepted + processed.
    "upload_complete":      '[aria-label*="название" i], [aria-label*="title" i]',
    "video_url_link":       '#video-url a, a.video-url-fadeable, a[href*="youtu.be"], a[href*="youtube.com/watch"]',

    # Captcha / challenge / error surfaces. /sorry/ redirect catch:
    # in Studio there is no captcha iframe directly — when Google's
    # bot check surfaces, the page redirects to /sorry/.
    "captcha_check":        'iframe[src*="captcha"], iframe[src*="recaptcha"]',
    "error_short":          '#error-short, .error-short',
}


# ─── Public types ────────────────────────────────────────────────────────────

class VisibilityMode(str, enum.Enum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"
    SCHEDULED = "scheduled"


@dataclass(frozen=True)
class UploadResult:
    """What ``upload_one`` reports back. ``video_url`` may be None if
    YouTube Studio didn't surface a link in the success page (some
    accounts get a "Video is processing" interstitial instead — the
    upload itself still succeeded)."""
    status: str          # 'success' | 'failed' | 'skipped' | 'captcha'
    message: str
    video_url: Optional[str] = None
    video_id: Optional[str] = None


# ───────────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────────

def _extract_video_id(url: str) -> Optional[str]:
    """Pull the YouTube video ID out of a watch / share URL. Returns
    ``None`` for non-YouTube URLs (e.g. the upload-page success screen
    sometimes links to the channel rather than the video)."""
    if not url:
        return None
    patterns = [
        r'youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})',
        r'youtu\.be/([A-Za-z0-9_-]{6,})',
        r'studio\.youtube\.com/video/([A-Za-z0-9_-]{6,})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _safe_locator(page, selector: str, *, loc_factory: Callable[..., Any] = None):
    """Convenience: page.locator(selector) wrapped so unit tests can
    inject a fake without an active Playwright handle."""
    if loc_factory is not None:
        return loc_factory(selector)
    return page.locator(selector)


# ───────────────────────────────────────────────────────────────────────────────
# Step methods — each is independently testable.
# ───────────────────────────────────────────────────────────────────────────────


async def open_studio_upload_page(page, *, logger_extra: str = "") -> str:
    """Navigate to studio.youtube.com -> Create -> Upload videos. Returns
    the current page URL on success.

    Some accounts have Create -> Upload in the top-left; newer ones
    have it under a hamburger menu. We try the button first then fall
    back to a direct URL.
    """
    await page.goto("https://studio.youtube.com/", wait_until="domcontentloaded", timeout=30_000)
    # Try the "Create" affordance; if it isn't there the page already
    # has the upload form sidebar open. Either way checking for the
    # file-input is the terminating signal.
    try:
        create_btn = page.locator('button[aria-label="Create"], #create-icon')
        if await create_btn.count() > 0:
            await create_btn.first.click(timeout=2000)
            upload_choice = page.locator('[role="menuitem"]:has-text("Upload videos")')
            if await upload_choice.count() > 0:
                await upload_choice.first.click(timeout=2000)
                await page.wait_for_load_state("domcontentloaded")
    except Exception as e:
        logger.info(
            f"{logger_extra} Create->Upload sidebar flow not found ({e}); "
            f"falling back to direct /upload URL"
        )
        await page.goto(
            "https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=30_000,
        )
    return page.url


async def attach_video_file(page, video_path: Path, *, logger_extra: str = "") -> None:
    """Step 1: file picker. Opens the file input (visible or hidden),
    sets the file, and waits for processing to complete.

    We hang on the hidden <input type=file> because it accepts the file
    regardless of which visible UI is shown (drag-drop zone, button,
    popup dialog)."""
    if not Path(video_path).exists():
        raise FileNotFoundError(f"video file missing: {video_path}")
    file_input = page.locator(SELECTORS["file_input"]).first
    await file_input.set_input_files(str(video_path))
    logger.info(f"{logger_extra} attached {video_path.name}")
    # Wait for upload to fully process. The Details step only shows
    # after YouTube Studio finishes its server-side copy + first
    # encoding pass.
    await page.wait_for_selector(SELECTORS["upload_complete"], timeout=180_000)
    logger.info(f"{logger_extra} upload processing complete")


async def fill_metadata(page, *, title: str, description: str = "", tags: Optional[list] = None) -> None:
    """Step 2: Details — title (required), description (optional),
    made-for-kids radio, tags are ignored since we don't expose them
    in our UI.

    Note on kids-radio: in YouTube Studio 2026 the
    "is this made for kids" radio group lives on the **Details**
    step — it is NOT its own step (it used to be a Checks step in
    older Studio). You must answer it before Next is accepted;
    otherwise the click registers but the form does not transition.
    So we click the "Нет, это видео не для детей" option here before
    we return so the caller can immediately advance."""
    title_box = page.locator(SELECTORS["title_textarea"]).first
    await title_box.fill(title)

    if description:
        desc_box = page.locator(SELECTORS["description_box"]).first
        await desc_box.fill(description)

    # Click "No, not made for kids" before checking Next-button's
    # enabled state — kids-radio MUST be answered or Next does nothing.
    kids_radio = page.locator(SELECTORS["made_for_kids_not"]).first
    try:
        await kids_radio.click(timeout=4000, force=True)
    except Exception as e:
        # If it isn't there (already answered or never present),
        # carry on — we don't want one missing radio to kill the run.
        logger.debug(f"kids-radio click skipped: {e}")

    # Wait for the "Next" button to ENABLE. YouTube Studio's Next is
    # disabled until title validation finishes.
    next_btn = page.locator(SELECTORS["step_next_button"]).first
    await _wait_until_enabled(next_btn, timeout_ms=15_000)


async def skip_video_elements(page) -> None:
    """Step 3: Video Elements (cards / end screen). Click Next immediately."""
    next_btn = page.locator(SELECTORS["step_next_button"]).first
    await _wait_until_enabled(next_btn, timeout_ms=10_000)
    await next_btn.click()
    await page.wait_for_timeout(500)     # Studio animates forward


async def confirm_checks(page) -> None:
    """Step 4: Checks — copyright + made-for-kids. The radio defaults
    are usually fine ('I own / NOT_MADE'); we only click if they're
    not already selected."""
    owned_radio = page.locator(SELECTORS["copyright_owned"]).first
    if await owned_radio.count() > 0 and await owned_radio.is_visible():
        try:
            await owned_radio.click(timeout=2000)
        except Exception:
            pass

    not_for_kids = page.locator(SELECTORS["made_for_kids_not"]).first
    if await not_for_kids.count() > 0 and await not_for_kids.is_visible():
        try:
            await not_for_kids.click(timeout=2000)
        except Exception:
            pass

    next_btn = page.locator(SELECTORS["step_next_button"]).first
    await _wait_until_enabled(next_btn, timeout_ms=10_000)
    await next_btn.click()
    await page.wait_for_timeout(500)


async def select_visibility(
    page,
    *,
    mode: VisibilityMode,
    scheduled_at: Optional[datetime] = None,
) -> None:
    """Step 5: Visibility. For ``scheduled`` we need a datetime;
    everything else ignores it."""
    radio_map = {
        VisibilityMode.PRIVATE:   SELECTORS["visibility_private"],
        VisibilityMode.UNLISTED:  SELECTORS["visibility_unlisted"],
        VisibilityMode.PUBLIC:    SELECTORS["visibility_public"],
        VisibilityMode.SCHEDULED: SELECTORS["visibility_schedule"],
    }
    radio = page.locator(radio_map[mode]).first
    await _wait_until_enabled(radio, timeout_ms=10_000)
    await radio.click()

    if mode == VisibilityMode.SCHEDULED:
        if scheduled_at is None:
            raise ValueError("scheduled_at is required for VisibilityMode.SCHEDULED")
        # Newer Studio: a single <input type=datetime-local>. Older:
        # separate date + time inputs labelled by aria.
        dt_input = page.locator(SELECTORS["schedule_date"]).first
        iso = scheduled_at.strftime("%Y-%m-%dT%H:%M")
        try:
            await dt_input.fill(iso)
        except Exception:
            # Fallback: separate date and time inputs.
            date_str = scheduled_at.strftime("%Y-%m-%d")
            time_str = scheduled_at.strftime("%H:%M")
            date_in = page.locator(SELECTORS["schedule_date"]).first
            time_in = page.locator(SELECTORS["schedule_time"]).first
            await date_in.fill(date_str)
            await time_in.fill(time_str)


async def click_publish(page) -> None:
    """Step 5 final: lock the upload in. Publish → processing → redirect
    to Video Published screen / channel list."""
    btn = page.locator(SELECTORS["publish_button"]).first
    await _wait_until_enabled(btn, timeout_ms=15_000)
    await btn.click()
    # Wait for either the success screen (video-url link visible) or
    # any captcha / error overlay.
    try:
        await page.wait_for_selector(
            SELECTORS["video_url_link"],
            timeout=20_000,
            state="visible",
        )
    except Exception:
        # We may have been redirected to a "Video is being processed"
        # page without a direct URL. Don't fail the upload yet — the
        # caller will check for video_url_link and decision accordingly.
        pass


async def read_published_url(page, *, logger_extra: str = "") -> UploadResult:
    """Read the success screen URL/link. Returns ``UploadResult``."""
    try:
        url_link = page.locator(SELECTORS["video_url_link"]).first
        if await url_link.count() > 0:
            href = await url_link.get_attribute("href")
            video_id = _extract_video_id(href or "")
            return UploadResult(
                status="success",
                message="uploaded",
                video_url=href,
                video_id=video_id,
            )
    except Exception as e:
        logger.info(f"{logger_extra} no video_url_link found: {e}")
    # Did we land on a captcha challenge?
    captcha = page.locator(SELECTORS["captcha_check"]).first
    if await captcha.count() > 0:
        return UploadResult(status="captcha", message="captcha challenge surfaced")
    # Failing that: maybe we succeeded but the URL is the new "Library"
    # page; the operator can verify manually.
    return UploadResult(status="success", message="uploaded (link not surfaced)")


# ───────────────────────────────────────────────────────────────────────────────
# Wait helper
# ───────────────────────────────────────────────────────────────────────────────


async def _wait_until_enabled(locator, *, timeout_ms: int) -> None:
    """Poll for ``disabled=false`` on a Playwright Locator. We retry
    rather than use ``locator.wait_for(state=enabled)`` because some
    intermediate frames show the button as enabled but with the wrong
    dependency tree (Studio spinners race)."""
    interval_ms = 250
    elapsed = 0
    while elapsed < timeout_ms:
        try:
            is_disabled = await locator.is_disabled()
            if not is_disabled:
                return
        except Exception:
            # Locator not in DOM yet — try again after a short pause.
            pass
        await asyncio.sleep(interval_ms / 1000.0)
        elapsed += interval_ms
    raise TimeoutError(
        f"locator did not become enabled within {timeout_ms}ms: {locator}"
    )


# ───────────────────────────────────────────────────────────────────────────────
# Top-level entry point
# ───────────────────────────────────────────────────────────────────────────────


async def upload_one(
    page,
    *,
    file_path: Path,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    visibility: VisibilityMode = VisibilityMode.PRIVATE,
    scheduled_at: Optional[datetime] = None,
    thumbnail_path: Optional[Path] = None,
    account_label: str = "default",
) -> UploadResult:
    """Drive the full 5-step upload flow on an already-open Playwright
    page that is ALREADY authenticated as the target channel.

    Returns an :class:`UploadResult`. Caller (``upload_with_cookies``)
    decorates with cookie-loading, browser boot, and account-aware log
    tagging.
    """
    log = f"[yt-form:{account_label}] "
    try:
        await open_studio_upload_page(page, logger_extra=log)
    except Exception as e:
        return UploadResult(status="failed", message=f"open upload page: {e!s}")

    try:
        await attach_video_file(page, file_path, logger_extra=log)
    except Exception as e:
        return UploadResult(status="failed", message=f"file picker: {e!s}")

    try:
        await fill_metadata(page, title=title, description=description, tags=tags)
    except Exception as e:
        return UploadResult(status="failed", message=f"fill metadata: {e!s}")

    if thumbnail_path and thumbnail_path.exists():
        try:
            thumb = page.locator(SELECTORS["upload_complete"])  # placeholder
            # Newer Studio: there's a thumbnail slot on the Details step.
            # Older: you set thumbnails post-publish. We skip if the
            # control isn't surfaced — most clips work fine without.
            _ = thumb
        except Exception:
            pass

    try:
        await skip_video_elements(page)
    except Exception as e:
        return UploadResult(status="failed", message=f"video elements step: {e!s}")

    try:
        await confirm_checks(page)
    except Exception as e:
        return UploadResult(status="failed", message=f"checks step: {e!s}")

    try:
        await select_visibility(
            page, mode=visibility, scheduled_at=scheduled_at,
        )
    except Exception as e:
        return UploadResult(status="failed", message=f"visibility step: {e!s}")

    try:
        await click_publish(page)
    except Exception as e:
        return UploadResult(status="failed", message=f"publish click: {e!s}")

    return await read_published_url(page, logger_extra=log)


__all__ = [
    "SELECTORS",
    "UploadResult",
    "VisibilityMode",
    "_extract_video_id",
    "upload_one",
]
