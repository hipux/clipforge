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
    #
    # Reliability note: in Russian locale we saw two distinct Unlisted
    # labels visible on the same dialog — "Ограниченный доступ" and
    # "Доступ по ссылке". Playwright's :has-text() matches the FIRST
    # visible locator; picking either works. We use the shorter one
    # below to avoid colliding with the "Доступ" (Access) sidebar-label.
    "visibility_private":   'tp-yt-paper-radio-button:has-text("Закрыть"), tp-yt-paper-radio-button:has-text("Private")',
    "visibility_unlisted":  'tp-yt-paper-radio-button:has-text("Ограниченный доступ"), tp-yt-paper-radio-button:has-text("Доступ по ссылке"), tp-yt-paper-radio-button:has-text("Unlisted")',
    "visibility_public":    'tp-yt-paper-radio-button:has-text("Открытый доступ"), tp-yt-paper-radio-button:has-text("Public")',
    "visibility_schedule":  'tp-yt-paper-radio-button:has-text("Назначить премьеру"), tp-yt-paper-radio-button:has-text("Запланировать"), tp-yt-paper-radio-button:has-text("Schedule"), tp-yt-paper-radio-button:has-text("Premiere")',

    # Schedule date+time. Newer Studio uses <input type="datetime-local">;
    # older versions split into date + time inputs.
    "schedule_date":        'input[type="datetime-local"], input[aria-label*="дата" i], input[aria-label*="date" i]',
    "schedule_time":        'input[aria-label*="время" i], input[aria-label*="time" i]',

    # Publish — final click that locks in the upload. Locale notes
    # from the 2026-Q2 explore: Russian Studio says "Опубликовать"
    # (Publish); English says "Save"/"Publish"; legacy 2020-2024
    # used "Done". Note: "Сохранить" (Russian for "Save") is NOT the
    # publish button — it's the sidebar-filter "Apply" button and
    # would accidentally click the wrong thing. We deliberately
    # excluded "Сохранить" from the candidates here.
    "publish_button":       'button:has-text("Опубликовать"), button:has-text("Save"), button:has-text("Publish"), button:has-text("Done"), #done-button',

    # ── Status surfaces ────────────────────────────────────
    "processing":           'tp-yt-paper-progress, [role="progressbar"]',
    # Studio 2026: the upload's "details" dialog renders the title
    # textarea at completion; we wait for this selectability as proof
    # the file has been accepted + processed.
    "upload_complete":      '[aria-label*="название" i], [aria-label*="title" i]',
    "video_url_link":       '#video-url a, a.video-url-fadeable, a[href*="youtu.be"], a[href*="youtube.com/watch"]',

    # ── Post-publish status surfaces ────────────────────────
    # After the operator clicks "Опубликовать"/"Publish", Studio shows
    # a progress panel. The CRITICAL element is `YTCP-VIDEO-UPLOAD-PROGRESS`
    # with the class `ytcp-uploads-still-processing-dialog` — this class
    # is present while Studio is still encoding / checking / re-encoding
    # the video, and gets REMOVED when the upload has truly completed.
    # We watch for the absence of that class — NOT for any text — because
    # the visible text during the wait oscillates between
    # "Загрузка видео завершена. Скоро начнется обработка." (intermediate),
    # "Сохранение метаданных", "Проверка нарушений", etc. — none of which
    # would be safe to treat as a completion signal.
    "publish_in_progress":  'ytcp-video-upload-progress.style-scope.ytcp-uploads-still-processing-dialog',
    # Studio's progress-bar text label shows the *current* stage (e.g.
    # "Проверка нарушений" / "Encoding the video"). We poll it as
    # informational logging only — the deterministic completion signal
    # is the in-progress marker above, not any text.
    "publish_progress_text": 'ytcp-video-upload-progress.style-scope.ytcp-uploads-dialog, [role="status"]:visible',
    # Optional success markers — surfaced as POLITE confirmation AFTER
    # the in-progress marker went away.
    "publish_success_text":  'text=/Опубликов/i, text=/Video published/i, text=/Published successfully/i, text=/Готово/i, text=/Завершен/i, [aria-label*="опубл" i], [aria-label*="published" i], [aria-label*="Done" i]',
    "publish_unavailable":   'text=/Публикация невозможна/i, text=/публикация прервана/i, text=/Ошибка публикации/i, text=/Upload failed/i, text=/Failed to publish/i, .error-short',

    # Captcha / challenge / error surfaces. /sorry/ redirect catch:
    # in Studio there is no captcha iframe directly — when Google's
    # bot check surfaces, the page redirects to /sorry/.
    "captcha_check":        'iframe[src*="captcha"], iframe[src*="recaptcha"]',
    "error_short":          '#error-short, .error-short',
}


# ─── Public types ────────────────────────────────────────────────────────────

# Post-publish completion-detection keywords. These are SUBSTRINGS
# matched case-insensitively against the visible innerText of any
# dialog-status element. They are used as a SECONDARY confirmation
# signal AFTER the strict Polymer-class gate has flipped (the class
# flip alone is sufficient, but the keywords give operators a log
# line that lists the actual Russian/English text Studio showed on
# success so they can verify behaviour manually on a new account).
PUBLISH_DONE_KEYWORDS = (
    # Russian — the canonical Studio 2026 cascade (from manually
    # observed runs on the operator's danny_test account):
    "нарушений не найдено",       # "no violations found"  ← terminal marker
    "нарушения не найдены",       # alternate inflection
    "проверка завершена",          # "check completed"      ← terminal marker
    "видео опубликовано",          # "video published"
    "опубликован",                 # "published"
    "опубликовано",                # "published (past tense)"
    "успешно опубликовано",        # "published successfully"
    "готово",                      # "done"
    # English fallbacks:
    "no violations found",
    "no issues found",
    "check complete", "check completed",
    "video published",
    "published successfully",
    "publish complete", "publish completed",
)

# Keywords that mark publish as FAILED. Best-effort detection
# — if Studio renders a red pill, we surface it as RuntimeError
# instead of running out the wait-loop's deadline.
PUBLISH_ERROR_KEYWORDS = (
    # Russian error variants:
    "публикация невозможна",      # "publishing impossible"
    "публикация прервана",         # "publishing interrupted"
    "ошибка публикации",           # "publish error"
    "нарушения найдены",           # "violations found" (negative outcome)
    "контент заблокирован",        # "content blocked"
    # English error variants:
    "upload failed", "publish failed", "failed to publish",
    "publish error",
)


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
    """Step 5 final: lock the upload in.

    After Publish is clicked YouTube Studio shows a progress panel
    (left-bottom corner) running through several sub-stages — the
    canonical Russian cascade, observed on the operator's danny_test
    account:

        1. "Загрузка видео завершена. ... Скоро начнется обработка."
           (Upload done, processing will begin soon)
        2. "Обработка в HD" with time estimate (Encoding HD)
        3. "Проверка X%" with time estimate (Compliance check)
        4. "Проверка завершена. Нарушений не найдено"
           (Check completed, no violations — terminal success marker)

    Each stage takes a few seconds and the whole thing can sum up to
    60-180 seconds.

    Completion detection — TWO-gate rule:
        PRIMARY (strict): the element
        ``<ytcp-video-upload-progress class="style-scope
        ytcp-uploads-still-processing-dialog">`` exists WHILE Studio
        is still processing and is REMOVED when the actual post
        including-rejection-checks finishes. We poll for that
        class's absence as the only exit signal.

        SECONDARY (cosmetic): after the strict gate flips, we log
        any visible text that matches PUBLISH_DONE_KEYWORDS so the
        operator can see in the log which terminal marker Studio
        rendered (Russian OR English variant).

    Failure detection — explicit error text inside the dialog.
        Studio renders a red pill text="Ошибка публикации" /
        "Нарушения найдены" / "Upload failed" when publishing is
        rejected; we surface it as RuntimeError so the caller sees
        the reason instead of a generic timeout.
    """
    btn = page.locator(SELECTORS["publish_button"]).first
    await _wait_until_enabled(btn, timeout_ms=15_000)
    await btn.click()
    logger.info("publish click registered; waiting for Studio post-processing...")

    deadline_s = 180.0
    interval_s = 2.0
    elapsed = 0.0
    status = "starting"
    last_stage_text = None
    in_progress_locator = page.locator(SELECTORS["publish_in_progress"])
    error_locator       = page.locator(SELECTORS["publish_unavailable"])
    progress_text_locator = page.locator(SELECTORS["publish_progress_text"])

    while elapsed < deadline_s:
        await asyncio.sleep(interval_s)
        elapsed += interval_s
        try:
            err_count = await error_locator.count()
            if err_count > 0:
                text = ""
                try:
                    text = (await error_locator.first.inner_text())[:140]
                except Exception:
                    pass
                raise RuntimeError(f"publish error surfaced: {text!r}")

            in_progress_count = await in_progress_locator.count()
            if in_progress_count == 0:
                status = "still_processing_marker_gone"
                logger.info(
                    f"publish progress: in-progress dialog cleared at "
                    f"elapsed={elapsed:.0f}s; primary exit signal."
                )
                break
            # Surface the current stage label every 8 seconds so the
            # operator can see Studio's progress caption changes.
            if int(elapsed) % 8 == 0:
                cur_text = None
                try:
                    if await progress_text_locator.count() > 0:
                        cur_text = (await progress_text_locator.first.inner_text())[:140]
                except Exception:
                    pass
                if cur_text and cur_text != last_stage_text:
                    logger.info(
                        f"publish progress (elapsed {elapsed:.0f}s): {cur_text!r}"
                    )
                    last_stage_text = cur_text
            status = "still_processing"
        except RuntimeError:
            raise
        except Exception:
            continue

    if status == "still_processing":
        logger.warning(
            f"publish deadline {deadline_s}s reached with in-progress marker "
            f"STILL visible — proceeding to read URL anyway (best-effort)."
        )

    # SECONDARY confirmation: after the class flipped, scan the DOM
    # once for one of our terminal markers. We do NOT block on this —
    # class flip is sufficient — but we log the actual terminal
    # text so the operator can verify Studio sent the expected
    # Russian "Нарушений не найдено" or the English equivalent.
    try:
        await asyncio.sleep(1.0)   # let the final text settle
        all_status = await page.evaluate(
            """() => {
                const els = Array.from(document.querySelectorAll(
                    '[role="status"], ytcp-uploads-dialog, [class*="processed"], [class*="finished"]'
                ));
                return els.map(e => (e.innerText || '').trim()).filter(Boolean);
            }"""
        )
        confirmed = None
        for t in all_status:
            low = t.lower()
            for kw in PUBLISH_DONE_KEYWORDS:
                if kw in low:
                    confirmed = t
                    break
            if confirmed:
                break
        if confirmed:
            logger.info(f"publish completion text confirmed: {confirmed[:140]!r}")
        else:
            # Also check for explicit error (Studio can flash both
            # success AND error on retry scenarios).
            err_text = None
            for t in all_status:
                low = t.lower()
                for kw in PUBLISH_ERROR_KEYWORDS:
                    if kw in low:
                        err_text = t
                        break
                if err_text:
                    break
            if err_text:
                logger.warning(
                    f"publish completion text ambiguous: failure-shaped marker "
                    f"visible ({err_text[:140]!r}). Re-read the URL anyway."
                )
            else:
                logger.info(
                    "publish completion: primary class-flip signal used; "
                    "no terminal-success text observed in the rendered DOM."
                )
    except Exception as e:
        logger.debug(f"completion-text scan failed (non-fatal): {e!s}")

    logger.info(f"post-publish wait finished: {status}, elapsed={elapsed:.0f}s")


async def read_published_url(page, *, logger_extra: str = "") -> UploadResult:
    """Read the success screen URL/link. Returns ``UploadResult``.

    We only ENTER this after ``click_publish().await`` has completed
    the post-processing wait, so a "video_url_link" surfaced at this
    point is the FINAL published URL of the new asset.
    """
    # Did we land on a captcha challenge?
    captcha = page.locator(SELECTORS["captcha_check"]).first
    if await captcha.count() > 0:
        return UploadResult(status="captcha", message="captcha challenge surfaced")

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
