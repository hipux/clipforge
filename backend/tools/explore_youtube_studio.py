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


def _safe_slug(s: str) -> str:
    """Make ``s`` filename-safe. We only need this so the snapshot
    label reflects the URL without breaking the OS filesystem."""
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in s)[:32] or "unknown"


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
        # We snapshot every observed step. We stop when we detect
        # Visibility radio buttons (the final step) OR no URL change
        # for 10 seconds.
        next_button_selectors = [
            'button:has-text("Next")',
            'button:has-text("Далее")',
            'button:has-text("Continue")',
            'button[aria-label="Next"]',
            'button[aria-label="Далее"]',
            '#next-button',
            'tp-yt-paper-icon-button[aria-label="Next"]',
            # Material Lit "trailing" button — newer Studio
            '.ytcpRightPinnedButton button',
            'button.ytcpRightPinnedButton',
        ]

        while step_index < 6:
            # Try to find a visible, clickable Next button.
            clicked = await _try_click_any(page, next_button_selectors, per_timeout_ms=4000)
            if clicked is None:
                # Could be on the very final step or stuck on a
                # step that needs a different action (e.g. kids
                # radio). Capture diagnostic snapshot then stop.
                await _snapshot_step(99, f"next_absent_{step_index}")
                logger.info(
                    f"Next button absent at step {step_index}. "
                    f"Final URL: {page.url}. See {snap_dir}/99_next_absent*.html"
                )
                break
            logger.info(f"step {step_index} -> Next clicked via {clicked}")
            elapsed = await _wait_steady(steady_seconds=8.0)
            if elapsed >= 8.0:
                # DOM fingerprint didn't change for 8s after the Next
                # click — assume we ARE on the final step (Visibility)
                # OR stuck because kids-radio wasn't answered.
                await _snapshot_step(step_index, "final_no_change")
                break
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
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
