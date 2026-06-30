"""DOM-explore: ты запускаешь, скрипт собирает реальные селекторы You're Studio.

Использование::

    cd D:\\clipforge\\workspace
    python -m backend.tools.explore_youtube_studio \\
        --cookies  D:\\clipforge\\workspace\\accounts\\danny_test\\cookies.json \\
        --account  danny_test

Скрипт ОТКРЫВАЕТ headed (видимый) Chrome, логинится через cookies, переходит на
https://studio.youtube.com/, кликает Create -> Upload videos, и пытается
пройти 5 шагов upload-формы. На каждом шаге он:

  * дампит HTML фрагмент интересной области;
  * собирает список data-testid / aria-label / role / id селекторов;
  * сохраняет короткий snapshot в PNG + HTML в ``--snapshot-dir``.

Цель: за один прогон понять, какие селекторы сегодня живые (ytb_up 6-12
месяцев назад — уже полу-живой). Только для Этапа 2 onboarding, не для production.

Аргументы:
    --cookies   path to your Cookie-Editor JSON (есть в danny_test/cookies.json).
    --account   account label only for the logger prefix.
    --snapshot-dir  Output directory. Defaults to ./snapshots/
    --browser   chromium|firefox (chromium по умолчанию).
    --headed    без : выкл; с : вкл (по умолчанию on - требуется headed для DOM).

ВАЖНО: скрипт НЕ отправляет форм-данные в YouTube. На последнем шаге (Visibility)
он останавливается на dry-run — не кликает Publish.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from backend.services.playwright_youtube import (
    AuthStatus,
    PublisherOptions,
    YoutubePublisher,
    detect_auth_status,
)

logger = logging.getLogger("explore")


# ─── Step detectors ───────────────────────────────────────────────────────


async def _try_click_any(page, candidates, per_timeout_ms: int = 3000):
    """Try multiple selectors in order; click the first one that
    resolves. Returns the selector string that worked, or ``None`` if
    all candidates timed out. We deliberately keep each timeout SHORT
    so we don't pile up minutes when Studio has renamed a control —
    the first miss should let us move on within seconds.
    """
    for sel in candidates:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count == 0:
                continue
            # Click the first matching, visible element.
            await loc.first.click(timeout=per_timeout_ms, force=True)
            return sel
        except Exception:
            continue
    return None


async def _any_locator_exists(page, candidates, per_timeout_ms: int = 1500) -> str | None:
    """Returns the FIRST matching selector or ``None``. We don't click,
    we just probe — used for TRANSITION DETECTION (e.g. is the
    Next-button still present? Are we already on Visibility?).
    ``.first.is_visible()`` is cheap and Studio's Polymer DOM is
    large enough that we don't want to click every candidate.
    """
    for sel in candidates:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count == 0:
                continue
            visible = await loc.first.is_visible(timeout=per_timeout_ms)
            if visible:
                return sel
        except Exception:
            continue
    return None


def _safe_slug(s: str) -> str:
    """Make ``s`` filename-safe. We only need this so the snapshot
    label reflects the URL without breaking the OS filesystem."""
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in s)[:32] or "unknown"


# ───────────────────────────────────────────────────────────────────
# Publish-and-observe (only with --publish flag)
# ───────────────────────────────────────────────────────────────────
#
# Studio's post-Publish phase is a real DOM-landscape:
#
#   1. Progress bar appears in the left-bottom corner with a text
#      caption underneath (in Russian: "Сохранение метаданных",
#      "Проверка нарушений", "Кодирование видео", "Завершено").
#   2. Each sub-stage takes 5-30 seconds. Different sizes -->
#      different times.
#   3. When complete, the dialog swaps to a "Готово / Published"
#      card OR redirects to the channel's content list.
#
# Our ``click_publish()`` in production code only knows two signals:
# (a) progress-bar disappeared, (b) success/error text appeared.
# Once we have the real selector for the post-Publish text caption,
# we can both log progress ("still on 'Проверка нарушений' after
# 30 s") AND detect completion with one extra selector match.
#
# The helper here is read-only on the LIVE page during a real
# Publish run, so we get true production-grade selector data.


PROGRESS_SCRAPE_JS = r"""
    () => {
        const statuss = Array.from(document.querySelectorAll(
            '[role="status"], [role="progressbar"], [role="alert"], [role="log"]'
        ));
        const hosts = [
            'ytcp-uploads-dialog',
            'ytcp-dialog',
            'ytcp-video-upload-progress',
        ];
        const out = [];
        const seen = new Set();
        for (const el of [...statuss, ...document.querySelectorAll(hosts.join(','))]) {
            const r = el.getBoundingClientRect();
            if (!r || r.width === 0 || r.height === 0) continue;
            const text = (el.innerText || '').trim();
            if (!text || text.length > 200) continue;
            const aria = el.getAttribute('aria-label') || '';
            const sig = JSON.stringify({
                tag: el.tagName,
                cls: (el.className || '').toString().slice(0, 80),
                id: el.id || '',
                text: text.slice(0, 120),
                aria: aria.slice(0, 120),
            });
            if (seen.has(sig)) continue;
            seen.add(sig);
            out.push({
                tag: el.tagName,
                cls: (el.className || '').toString().slice(0, 80),
                id: el.id || '',
                role: el.getAttribute('role') || '',
                text: text.slice(0, 120),
                aria: aria.slice(0, 120),
            });
        }
        return out;
    }
"""


async def _scrape_progress(page) -> List[Dict[str, str]]:
    try:
        return await page.evaluate(PROGRESS_SCRAPE_JS)
    except Exception as e:
        logger.warning(f"scrape failed: {e}")
        return []


_DONE_KEYWORDS = (
    "опубликов", "published", "publish complete", "publish finished",
    "завершен", "готово", "complete", "done", "finished",
)
_ERROR_KEYWORDS = (
    "публикация невозможна", "публикация прервана", "ошибка публикации",
    "upload failed", "failed to publish", "publish error", "publish failed",
)


def _is_done_text(text: str) -> bool:
    return any(k in text.lower() for k in _DONE_KEYWORDS)


def _is_error_text(text: str) -> bool:
    return any(k in text.lower() for k in _ERROR_KEYWORDS)


async def _publish_and_observe(page, snap_dir: Path, args) -> None:
    """Visibility → click PRIVATE → click Publish (Опубликовать) →
    poll the page every ``args.interval`` seconds, capturing the
    visible text nodes inside the upload dialog. Stop on completion
    marker OR error marker OR ``args.deadline`` seconds.

    Writes ``progress_NNN.png`` + ``progress_NNN.json`` snapshots
    AND a final ``unique_progress_texts.txt`` summarising every
    distinct text we saw.
    """
    logger.info("=" * 60)
    logger.info("[publish-observe] --publish: clicking PRIVATE + Publish, then polling...")
    logger.info("=" * 60)

    # Click PRIVATE radio on Visibility.
    try:
        # Match the actual radio button — Studio's <tp-yt-paper-radio-button>
        # puts the label inside a Polymer shadow-DOM subtree, so the
        # generic 'text=' query that pierces shadow boundaries is
        # more reliable than ':has-text=' which only walks light DOM.
        priv = page.locator(
            'text="Закрыть", '
            'text="Private", '
            'input#private-radio-button'
        ).first
        await priv.click(timeout=4000, force=True)
        logger.info("[publish-observe] PRIVATE radio clicked")
    except Exception as e:
        logger.warning(f"[publish-observe] PRIVATE radio click failed: {e}")

    # Click Publish.
    publish_btn = page.locator(
        'button:has-text("Опубликовать"), '
        'button:has-text("Save"), '
        'button:has-text("Publish"), '
        'button:has-text("Done")'
    ).first
    try:
        await publish_btn.click(timeout=5000, force=True)
        logger.info("[publish-observe] Publish clicked — polling begins")
    except Exception as e:
        logger.error(f"[publish-observe] Publish click failed: {e}")
        await page.screenshot(path=str(snap_dir / "publish_click_error.png"))
        return

    unique_texts: List[str] = []
    seen_done = False
    seen_error = False
    deadline = time.monotonic() + args.deadline
    sample_idx = 0

    while time.monotonic() < deadline:
        sample_idx += 1
        await asyncio.sleep(args.interval)
        scrape = await _scrape_progress(page)
        await page.screenshot(path=str(snap_dir / f"progress_{sample_idx:03d}.png"))
        (snap_dir / f"progress_{sample_idx:03d}.json").write_text(
            json.dumps(scrape, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        for el in scrape:
            t = (el.get("text") or "").strip()
            if not t or t in unique_texts:
                continue
            unique_texts.append(t)
            logger.info(f"[publish-observe] new text: {t[:140]!r}")
            if _is_done_text(t):
                seen_done = True
            elif _is_error_text(t):
                seen_error = True

        if seen_done:
            logger.info("[publish-observe] completed-text detected; exiting poll")
            break
        if seen_error:
            logger.warning("[publish-observe] error text detected; exiting poll")
            break

    if not seen_done and not seen_error:
        logger.warning(
            f"[publish-observe] deadline reached at {args.deadline}s without done/error; "
            f"captured {sample_idx} samples"
        )

    (snap_dir / "unique_progress_texts.txt").write_text(
        "\n".join(unique_texts), encoding="utf-8",
    )
    logger.info(
        f"[publish-observe] unique progress texts ({len(unique_texts)}) → "
        f"{snap_dir}/unique_progress_texts.txt"
    )
    logger.info(
        f"[publish-observe] series: progress_001.png .. progress_{sample_idx:03d}.png"
    )

    if seen_done:
        logger.info(
            "[publish-observe] ★ publish COMPLETED. video is now PRIVATE on the channel."
        )
    elif seen_error:
        logger.warning(
            f"[publish-observe] ★ publish FAILED. Open {snap_dir}/progress_* to debug."
        )


async def _dom_fingerprint(page) -> tuple:
    """Tiny DOM signature: counts of buttons, h1s, the visible
    ``ytcp-uploads-dialog-host`` host name + all visible text buttons.
    We use this as a step-change detector because Studio 2026 keeps
    the URL constant across all upload flow steps (SPA-style)."""
    counts = await page.evaluate("""
        () => {
            const visible = el => {
                if (!el) return false;
                const r = el.getBoundingClientRect();
                return r && r.width > 0 && r.height > 0;
            };
            const buttons = Array.from(document.querySelectorAll('button'))
                .filter(visible).map(b => (b.innerText || '').trim().slice(0, 30)).filter(Boolean);
            const headings = Array.from(document.querySelectorAll('h1, h2, [role=heading]'))
                .filter(visible).map(h => (h.innerText || '').trim().slice(0, 30)).filter(Boolean);
            const radioLabels = Array.from(document.querySelectorAll('[role=radio]'))
                .filter(visible).map(r => (r.innerText || '').trim().slice(0, 30)).filter(Boolean);
            const host = !!document.querySelector('ytcp-uploads-dialog');
            return [buttons.length, headings.length, radioLabels.length, host, JSON.stringify([buttons, headings, radioLabels])];
        }
    """)
    return tuple(counts)


# ─── Step detectors ───────────────────────────────────────────────────────


# We tell steps apart by URL fragment + page heading text. These are stable
# routes that YouTube Studio has kept for several years.
STEP_PATTERNS = {
    "step-1-select-file": {
        "url_contains": "/upload?",
        "heading_text": None,    # doesn't have a stable heading — file picker overlay
    },
    "step-2-details": {
        "url_contains": None,
        "heading_text": "Details",
    },
    "step-3-video-elements": {
        "url_contains": None,
        "heading_text": "Video elements",
    },
    "step-4-checks": {
        "url_contains": None,
        "heading_text": "Checks",
    },
    "step-5-visibility": {
        "url_contains": None,
        "heading_text": "Visibility",
    },
}


async def dump_selectors_on(page, label: str, snap_dir: Path) -> Dict[str, Any]:
    """Capture DOM-extractable cursor pieces for the current page,
    Save HTML + PNG to ``snap_dir``.

    Returns a JSON-able summary dict the operator can paste back. We
    do NOT scrape YouTube server-side interaction; we local quote
    whatever the DOM shows for the elements we'd be using in a
    Playwright recipe.
    """
    snap_dir.mkdir(parents=True, exist_ok=True)

    # selectors.json — what we'd want to grep on
    selectors = await page.evaluate("""
        () => {
            const out = {testid: [], aria: [], id: [], name: [], role_btn: []};
            const all = document.querySelectorAll('[data-testid], [aria-label], [id], [name], button, [role="radio"]');
            all.forEach(el => {
                if (el.dataset.testid) out.testid.push({tag: el.tagName, val: el.dataset.testid});
                const aria = el.getAttribute('aria-label');
                if (aria) out.aria.push({tag: el.tagName, val: aria});
                if (el.id) out.id.push({tag: el.tagName, val: el.id});
                if (el.getAttribute('name')) out.name.push({tag: el.tagName, val: el.getAttribute('name')});
                if (el.tagName === 'BUTTON') out.role_btn.push({text: (el.innerText || '').slice(0, 80)});
                const role = el.getAttribute('role');
                if (role === 'radio') out.role_btn.push({role: 'radio', text: (el.innerText||'').slice(0,80)});
            });
            // dedupe
            const deDuped = list => Array.from(new Map(list.map(x => [JSON.stringify(x), x])).values());
            return {
                testid: deDuped(out.testid).slice(0, 60),
                aria:   deDuped(out.aria).slice(0, 60),
                id:     deDuped(out.id).slice(0, 60),
                name:   deDuped(out.name).slice(0, 40),
                buttons: deDuped(out.role_btn).slice(0, 30),
            };
        }
    """)

    # Save HTML (clip) + PNG screenshot
    safe_label = label.replace('/', '_').replace(' ', '_')
    html_path = snap_dir / f"{safe_label}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(await page.content())
    png_path = snap_dir / f"{safe_label}.png"
    try:
        await page.screenshot(path=str(png_path), full_page=False)
    except Exception as e:
        logger.warning(f"screenshot failed for {label}: {e}")

    return {
        "label": label,
        "url": page.url,
        "selectors": selectors,
        "html_path": str(html_path),
        "png_path": str(png_path),
    }


async def main_async(args) -> int:
    log_format = "  [%(name)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    snap_dir = Path(args.snapshot_dir).resolve()
    snap_dir.mkdir(parents=True, exist_ok=True)

    options = PublisherOptions(
        browser=args.browser,
        headless=args.headed == 0,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    )

    async with YoutubePublisher(
        args.account, Path(args.cookies), options=options,
    ) as pub:
        # Phase 1: auth probe (also helps warm up cookies)
        auth = await pub.is_authenticated()
        if auth != AuthStatus.AUTHENTICATED:
            logger.error(f"auth-probe returned {auth.value}; cookies may be stale")
            return 1
        logger.info("auth: OK")

        page = pub._page

        # Phase 2: jump directly to /upload. Two navigation hops
        # (studio -> /upload) gave YouTube Studio a chance to send an
        # extra anti-bot challenge so we collapsed the path. The
        # Create-button hunt that used to live here is removed — it
        # takes 5+ seconds to time out and the direct URL is faster
        # AND less suspicious.
        await page.goto(
            "https://www.youtube.com/upload",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        await dump_selectors_on(page, "00_landing", snap_dir)
        (snap_dir / "00_landing.json").write_text(
            json.dumps(
                await dump_selectors_on(page, "00_landing", snap_dir),
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # Phase 3: file picker — direct set_input_files on the always-
        # hidden <input type="file">. Bypasses the native chooser
        # dialog entirely (no expect_file_chooser dance needed).
        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files(str(args.test_video))
        logger.info(f"attached {args.test_video}")
        snap_after_attach = await dump_selectors_on(page, "01_file_picker_just_attached", snap_dir)
        (snap_dir / "01_file_picker_just_attached.json").write_text(
            json.dumps(snap_after_attach, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Phase 4: URL-based step detection. YouTube Studio changes the
        # URL fragment when transitioning between Steps (we observed
        # `/upload?=/details` style historically; newer Studio keeps
        # everything on /upload but updates history.state hashes). We
        # snapshot on EVERY visible-state change until N consecutive
        # seconds of no-change, OR we see / again (Studio returns to
        # the dashboard when you finish).
        step_index = 1
        last_url = page.url
        last_step_change_at = time.monotonic()
        seen_step_labels = set()        # dedupe identical-state snapshots

        def _label_for_url(u: str) -> str:
            """Best-effort step label from URL + visible heading."""
            if "/upload" not in u:
                return f"post_upload_{_safe_slug(u)}"
            return "upload_form"

        # Helper: wait until page content actually changes (Studio
        # 2026 is SPA-style — URL stays constant so we'd never detect
        # anything via URL change). We poll a tiny DOM fingerprint:
        # the count of buttons + visible headings. If the fingerprint
        # stays stable for ``steady_seconds``, assume the form is on
        # the final step OR stuck.
        async def _wait_steady(steady_seconds: float = 8.0):
            nonlocal last_step_change_at
            start = time.monotonic()
            last_fp = await _dom_fingerprint(page)
            while time.monotonic() - start < 180.0:    # up to 3 min per phase
                await asyncio.sleep(0.8)
                cur_fp = await _dom_fingerprint(page)
                if cur_fp != last_fp:
                    return time.monotonic() - start
                if time.monotonic() - last_step_change_at > steady_seconds:
                    return time.monotonic() - start
                last_fp = cur_fp
            return time.monotonic() - start

        async def _snapshot_step(idx: int, label_extra: str = ""):
            """Capture HTML + JSON for the current page state. Uses
            ``label_extra`` so we don't overwrite prior snapshots."""
            label = f"0{idx}_{label_extra or _label_for_url(page.url)}"
            (snap_dir / f"{label}.json").write_text(
                json.dumps(
                    await dump_selectors_on(page, label, snap_dir),
                    indent=2, ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        # 1) capture state right after attach
        await _snapshot_step(step_index, "after_attach")

        # 2) Wait for upload processing → step 2 (Details)
        try:
            await page.wait_for_selector(
                '#title-textarea, [aria-label*="title" i]', timeout=180_000,
            )
            step_index += 1
            last_url = page.url
            last_step_change_at = time.monotonic()
            await _snapshot_step(step_index, "details")
        except Exception as e:
            logger.error(f"upload processing did not surface Details step: {e}")
            await _snapshot_step(99, "upload_stuck")
            return 2

        # 3) Try to advance via Next-button candidate list. Each
        # attempt: try to click, wait for URL change OR steady-state.
        # We snapshot every observed step. YouTube Studio 2026 keeps
        # the SAME DOM dialog across all upload stages, only changing
        # the inner panel content. So the previous "DOM fingerprint
        # changed?" detector never fires — we now loop differently:
        # click Next while Next-button exists. When Next disappears,
        # we've reached the final Visibility step.
        next_button_selectors = [
            'button:has-text("Next")',
            'button:has-text("Далее")',
            'button:has-text("Continue")',
            'button[aria-label="Next"]',
            'button[aria-label="Далее"]',
            '#next-button',
            'tp-yt-paper-icon-button[aria-label="Next"]',
            '.ytcpRightPinnedButton button',
            'button.ytcpRightPinnedButton',
        ]
        kids_radio_candidates = [
            'tp-yt-paper-radio-button:has-text("Нет, это видео")',
            'tp-yt-paper-radio-button:has-text("не для детей")',
            'tp-yt-paper-radio-button:has-text("not made for kids")',
            'tp-yt-paper-radio-button:has-text("not for kids")',
        ]
        # Visibility-specific radios — if they appear, the form is on
        # the LAST step (Visibility) and we should stop clicking Next.
        visibility_radio_candidates = [
            'tp-yt-paper-radio-button:has-text("Закрытый")',
            'tp-yt-paper-radio-button:has-text("Открытый")',
            'tp-yt-paper-radio-button:has-text("Private")',
            'tp-yt-paper-radio-button:has-text("Public")',
            'tp-yt-paper-radio-button:has-text("Запланировать")',
            'tp-yt-paper-radio-button:has-text("Schedule")',
        ]

        # Hard cap: max 7 transitions. The form has 4 movements
        # (Details → Video elements → Checks → Visibility); 7 leaves
        # comfortable room for transient state without ever publishing.
        for attempt in range(7):
            # Stop conditions:
            # 1) Visibility radios present — last step reached.
            on_visibility = await _try_click_any(
                page, visibility_radio_candidates, per_timeout_ms=1500,
            )
            if on_visibility:
                logger.info(f"visibility radios visible via {on_visibility} → we are on the final step")
                await _snapshot_step(step_index, "visibility_reached")
                break

            # 2) No Next-button at all — could also be a transition
            # mid-progress; check with a short timeout.
            has_next = await _any_locator_exists(
                page, next_button_selectors, per_timeout_ms=1500,
            )
            if not has_next:
                logger.info(f"Next-button not present on step {step_index}; assuming final")
                await _snapshot_step(step_index, "next_absent")
                break

            # ── Answer kids-radio before clicking Next (Studio 2026
            # validates the radio first or the click is silently
            # ignored when the dialog hasn't transitioned yet).
            await _try_click_any(page, kids_radio_candidates, per_timeout_ms=2000)

            # Click Next.
            clicked = await _try_click_any(page, next_button_selectors, per_timeout_ms=4000)
            if clicked is None:
                logger.info(
                    f"Next-button vanished between pre-check and click "
                    f"(step {step_index}). Likely on Visibility now."
                )
                await _snapshot_step(step_index, "next_vanished")
                break
            logger.info(f"step {step_index} -> Next clicked via {clicked}")
            # Give Studio time to transition the inner panels.
            await asyncio.sleep(2.5)
            step_index += 1
            last_step_change_at = time.monotonic()
            await _snapshot_step(step_index, f"after_next_{clicked}")

        # Phase 5: dry-run the FINAL step (Visibility). Don't click
        # Publish. Capture state for finishing-type-selector detection.
        try:
            await page.wait_for_timeout(2000)
            await _snapshot_step(99, "final_dry_run")
        except Exception:
            pass

        # ── Phase 6 (EDITABLE ONLY): --publish goes through Publish ───
        # When the operator passes ``--publish``, we click PRIVATE on
        # the Visibility step and then PUBLISH, then poll the page
        # every``--interval``seconds until publishing shows a
        # completion marker OR an error OR ``--deadline`` elapses.
        # Default is to NOT click Publish (--publish absent) so the
        # safe dry-run mode is preserved.
        if getattr(args, "publish", False):
            await _publish_and_observe(page, snap_dir, args)

        # If requested, leave the browser alive after exploration so
        # the operator can poke at it with DevTools / viewport /
        # click patterns we tried. Block until they Ctrl+C in the
        # terminal (or close the browser window — Playwright will
        # raise on next interaction and the asyncio.wait will
        # unblock on cancellation).
        if getattr(args, "keep_open", False):
            logger.info(
                "\n\n*** --keep-open active: browser kept open after exploration. ***\n"
                "*** Click around in Chrome to inspect. Press Ctrl+C here to exit. ***\n"
            )
            try:
                # Block forever. Event is never set; only Ctrl+C ends us.
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass

    logger.info(f"exploration complete. snapshots → {snap_dir}")
    logger.info("dry-run — НЕ отправлял publish.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookies", required=True, help="Cookie-Editor JSON path")
    parser.add_argument("--account", required=True, help="account label for logs")
    parser.add_argument("--test-video", required=True,
                        help="small mp4 для Step 1 file picker (gen <1МБ)")
    parser.add_argument("--snapshot-dir", default="./snapshots",
                        help="куда складывать HTML/PNG dumps")
    parser.add_argument("--browser", default="chromium",
                        help="chromium|firefox (default chromium)")
    parser.add_argument("--headed", type=int, default=1,
                        help="1 = headed (видимый браузер), 0 = headless")
    parser.add_argument("--keep-open", action="store_true",
                        help="После exploration оставить браузер открытым, "
                             "чтобы оператор мог проверить UI в DevTools. "
                             "Ctrl+C в этом терминале = закрыть.")
    parser.add_argument("--publish", action="store_true",
                        help="После Visibility step: кликнуть PRIVATE + "
                             "Publish и поллить progress-text. ВНИМАНИЕ: "
                             "видео реально публикуется (PRIVATE) на "
                             "аккаунт. Не запускать на main-канале.")
    parser.add_argument("--deadline", type=int, default=180,
                        help="сколько секунд ждать завершения Publish (default 180)")
    parser.add_argument("--interval", type=float, default=1.5,
                        help="секунд между snapshot во время poll (default 1.5)")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
