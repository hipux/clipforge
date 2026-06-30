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
        # Phase 1: auth probe
        auth = await pub.is_authenticated()
        if auth != AuthStatus.AUTHENTICATED:
            logger.error(f"auth-probe returned {auth.value}; cookies may be stale")
            return 1
        logger.info("auth: OK")

        # Phase 2: open upload page
        page = pub._page
        await page.goto("https://studio.youtube.com/", wait_until="domcontentloaded")
        # YouTube Studio's main page has Create->Upload in a sidebar / drawer.
        # Try the "Create" button (top-left). If absent, fallback to direct URL.
        try:
            await page.click('[aria-label="Create"]', timeout=5000)
            await page.click('[aria-label="Upload videos"]', timeout=5000)
        except Exception as e:
            logger.info(f"Create->Upload flow not found ({e}); using direct /upload URL")
            await page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded")

        # Phase 3: file picker
        # Use the FIRST input[type=file] on the page (it's hidden but Playwright
        # accepts file via set_input_files).
        file_input = page.locator('input[type="file"]').first
        async with page.expect_file_chooser(timeout=10_000) as fc_info:
            # Newer YT Studio: a "Select files" button that opens file chooser
            # OR an embedded drag-drop zone — the input is always in the
            # DOM regardless of UI variant.
            try:
                await page.click('button:has-text("Select files")', timeout=2000)
            except Exception:
                # Fall through — file input itself picks
                pass
            # We need to attach the file to the input. Even when the UI
            # uses a file chooser dialog, we set the input directly to
            # avoid the chooser subprocess dance.
            await file_input.set_input_files(args.test_video)
        page_summary = await dump_selectors_on(page, "01_file_picker", snap_dir)
        logger.info(f"snapshot 01_file_picker saved → {snap_dir}")

        # Phase 4: wait for upload-101 → then "Details" step
        # The upload completes when a "title textarea" appears next to a
        # progress bar that disappears.
        try:
            await page.wait_for_selector('#title-textarea', timeout=120_000)
        except Exception as e:
            logger.error(f"upload processing did not surface Details step: {e}")
            # Still dump whatever we got — useful for diagnosis.
            snapshot = await dump_selectors_on(page, "02_after_upload_fail", snap_dir)
            (snap_dir / "02_after_upload_fail.json").write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False)
            )
            return 2

        summary_details = await dump_selectors_on(page, "02_details", snap_dir)
        (snap_dir / "02_details.json").write_text(
            json.dumps(summary_details, indent=2, ensure_ascii=False)
        )

        # Phase 5: drive through remaining steps WITHOUT filling/saving.
        # The goal is to discover navigation patterns (Next button label,
        # optional skip buttons, visibility selector set). We just sniff.
        step_n = 2
        while step_n < 6:
            step_n += 1
            label = f"0{step_n}_step"
            try:
                # Try to detect step heading by content
                await page.wait_for_timeout(2000)
                snap = await dump_selectors_on(page, label, snap_dir)
                (snap_dir / f"{label}.json").write_text(
                    json.dumps(snap, indent=2, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"step {step_n} dump failed: {e}")
                break
            # Try to click Next to advance
            next_btn = page.locator('button:has-text("Next")').first
            try:
                await next_btn.click(timeout=3000)
                await page.wait_for_timeout(1500)
            except Exception:
                logger.info("Next button absent; assuming last step")
                break

        # Phase 6: dry-run final step (Visibility) — don't click Publish.
        try:
            await page.wait_for_timeout(2000)
            snap = await dump_selectors_on(page, "06_visibility_dryrun", snap_dir)
            (snap_dir / "06_visibility_dryrun.json").write_text(
                json.dumps(snap, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"final dump failed: {e}")

    logger.info(f"exploration complete. snapshots → {snap_dir}")
    logger.info("туp stop on form data: dry-run — НЕ отправлял publish.")
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
