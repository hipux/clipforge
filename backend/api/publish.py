"""Publishing API endpoints for YouTube.

Two upload paths supported (chosen by `PublishRequest.method`):
    - "official" — Google's YouTube Data API v3, paid Workspace required.
      Kept for users who already have credentials configured.
    - "browser"  — Playwright + cookies. The default — does not ping
      Google as an "official API client", so it won't trigger
      quota/automation flags for short-clip publishers.

Within the "browser" path, two implementation engines coexist during
Этап 2 of the ytb-up replacement:

  * `playwright` — our self-hosted :mod:`playwright_youtube` +
    :mod:`upload_form` flow. Activated by default since the new
    flow has no upstream-library breaking in 2024.
  * `ytb_up` — legacy wrapper around the third-party `ytb-up`
    package. Kept for A/B comparison and as a fallback while we
    finish Этап 3 (scheduling, batch, anti-bot).

    Toggle: env ``CLIPFORGE_PUBLISHER_BACKEND=playwright|ytb_up``,
    default ``playwright``.

Both paths return the same `PublishResponse` shape so the frontend
doesn't need to know which one ran.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
import subprocess
import sys
from backend.models import PublishRequest, PublishResponse, YouTubeAuthStatus
from backend.services.youtube_publisher import (
    upload_video_to_youtube,
    initiate_oauth_flow,
    complete_oauth_flow,
    is_authenticated
)
from backend.services.youtube_browser_publisher import (
    upload_with_cookies as _legacy_youtube_browser_upload,
    # Re-export under the old name so existing tests that
    # monkeypatch `pub_api.upload_with_cookies` keep working. The
    # new self-hosted flow ignores this attribute entirely — only
    # used when ``CLIPFORGE_PUBLISHER_BACKEND=ytb_up``.
    upload_with_cookies,
)
from backend.services.playwright_youtube import (
    YoutubePublisher,
    AuthStatus as PlaywrightAuthStatus,
    PublisherOptions,
)
from backend.services.upload_form import (
    upload_one as _playwright_upload_one,
    VisibilityMode as PlaywrightVisibility,
    UploadResult as PlaywrightUploadResult,
)
from backend.db import get_clip, save_publish_log, get_account, touch_account
from backend.config import OUTPUT_DIR, WORKSPACE_DIR

logger = logging.getLogger(__name__)

# Read once at import time. Empty string falls back to default.
PUBLISHER_BACKEND = (
    os.environ.get("CLIPFORGE_PUBLISHER_BACKEND", "playwright").strip().lower()
)

router = APIRouter()

# Where browser-method account cookies live.
COOKIES_DIR = WORKSPACE_DIR / "youtube_accounts"


@router.get("/auth/youtube", response_model=YouTubeAuthStatus)
async def get_youtube_auth_status():
    """Get YouTube authentication status or OAuth URL."""
    if is_authenticated():
        return YouTubeAuthStatus(authenticated=True)

    try:
        auth_url = initiate_oauth_flow()
        return YouTubeAuthStatus(authenticated=False, auth_url=auth_url)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate OAuth: {str(e)}")


@router.post("/auth/youtube/callback")
async def youtube_oauth_callback(auth_code: str):
    """Complete YouTube OAuth flow with authorization code."""
    success = complete_oauth_flow(auth_code)

    if success:
        return {'message': 'Successfully authenticated with YouTube', 'authenticated': True}
    else:
        raise HTTPException(status_code=400, detail='OAuth flow failed')


@router.post("/publish", response_model=PublishResponse)
async def publish_to_youtube(request: PublishRequest):
    """Upload a clip to YouTube — picks the official- or browser-method."""
    # Get clip from database
    clip = await get_clip(request.clip_id)

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if request.method == "browser":
        return await _publish_via_browser(clip, request)
    elif request.method == "official":
        return await _publish_via_official(clip, request)
    else:
        raise HTTPException(status_code=400,
                            detail=f"unknown publish method: {request.method!r}")


async def _publish_via_browser(clip, request: PublishRequest) -> PublishResponse:
    """Use Playwright + cookie auth. Default — looks like a real user.

    Backend is selected by env ``CLIPFORGE_PUBLISHER_BACKEND``:
      * ``playwright`` (default): our self-hosted flow
        (playwright_youtube.UploadForm 5-step dance).
      * ``ytb_up``: legacy thin wrapper around the third-party
        ``ytb-up`` package. Used during Этап 2 as a fallback if our
        new DOM flow breaks something.

    Account resolution order:
      1. Explicit `request.cookies_path` (UI override),
      2. `account.cookies_path` for the named account,
      3. Workspace fallback `<COOKIES_DIR>/<account_id or 'default'>/cookies.json`,
      4. `<COOKIES_DIR>/default/cookies.json` (legacy).
    """
    video_path = _absolute_clip_path(clip['file_path'])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"clip file missing: {video_path}")

    cookies_path: Path | None = None
    proxy: str | None = None
    if request.cookies_path:
        cookies_path = Path(request.cookies_path)
    elif request.account_id:
        # Load the account row so we honour its configured cookies_path /
        # proxy. None of these are required yet — operator may sign in later.
        account = await get_account(request.account_id)
        if account is None:
            raise HTTPException(status_code=404,
                                detail=f"account {request.account_id!r} not found")
        if account.get("cookies_path"):
            cookies_path = Path(account["cookies_path"])
        proxy = account.get("proxy") or None
    if cookies_path is None:
        cookies_path = COOKIES_DIR / (request.account_id or "default") / "cookies.json"

    if PUBLISHER_BACKEND == "ytb_up":
        # Use the bare ``upload_with_cookies`` name (not the private
        # alias) so monkeypatch-setattr on ``pub_api.upload_with_cookies``
        # in tests continues to work after we imported both names.
        result = await upload_with_cookies(
            file_path=video_path,
            title=request.title,
            description=request.description,
            tags=request.tags,
            cookies_path=cookies_path,
            proxy=proxy,
        )
        if result.status == "success":
            await _save_browser_publish_log(request, result.youtube_url)
        return _legacy_to_response(result, request)
    # === default: self-hosted Playwright ===================================
    return await _publish_via_playwright(video_path, cookies_path, request, proxy)


async def _save_browser_publish_log(request: PublishRequest, youtube_url: Optional[str]) -> None:
    """Persist the publish_log row + touch account, for the legacy
    path. The new playwright path does this inline so it can stream
    progress over the WebSocket; tests want a single source of truth
    they're already patching out."""
    await save_publish_log({
        'clip_id': request.clip_id,
        'platform': 'youtube',
        'youtube_url': youtube_url,
        'method': 'browser',
        'account_id': request.account_id,
    })
    if request.account_id:
        await touch_account(request.account_id)


def _legacy_to_response(result, request: PublishRequest) -> PublishResponse:
    """Map the legacy wrapper's ``PublishResult`` to our new envelope."""
    return PublishResponse(
        youtube_url=result.youtube_url,
        status=result.status,
        message=result.message,
    )


async def _publish_via_playwright(
    video_path: Path,
    cookies_path: Path,
    request: PublishRequest,
    proxy: Optional[str],
) -> PublishResponse:
    """Self-hosted Playwright upload flow. Boots Chromium, loads cookies,
    drives the 5-step YouTube Studio upload form.

    Этап 3 will add: scheduled publishing (now exposed as PRIVATE always),
    batch through asyncio queue, anti-bot UA rotator, captcha detection.
    """
    opts = PublisherOptions(
        headless=os.environ.get("CLIPFORGE_PUBLISHER_HEADLESS", "1") not in ("0", "false", "no"),
        proxy=proxy,
    )
    log_label = request.account_id or "default"
    async with YoutubePublisher(log_label, cookies_path, options=opts) as pub:
        from backend.services.playwright_youtube import detect_auth_status
        # Quick auth probe BEFORE we invest in attach_video_file — saves
        # a 200-MB upload if cookies expired.
        try:
            await pub.is_authenticated()
        except Exception as e:
            logger.warning(f"[yt-form:{log_label}] auth probe crashed: {e}")

        # Visibility: until Этап 3 ships scheduled publishing we
        # always upload as PRIVATE so the operator manually publishes
        # after the batch run. Этап 3 will read
        # ``request.scheduled_at`` and pick SCHEDULED instead.
        visibility = PlaywrightVisibility.PRIVATE

        result: PlaywrightUploadResult = await _playwright_upload_one(
            pub._page,
            file_path=video_path,
            title=request.title,
            description=request.description or "",
            tags=request.tags,
            visibility=visibility,
            account_label=log_label,
        )

    if result.status == "success":
        await save_publish_log({
            'clip_id': request.clip_id,
            'platform': 'youtube',
            'youtube_url': result.video_url,
            'method': 'browser',
            'account_id': request.account_id,
        })
        if request.account_id:
            await touch_account(request.account_id)
    return PublishResponse(
        youtube_url=result.video_url,
        status=result.status,
        message=result.message,
    )


async def _publish_via_official(clip, request: PublishRequest) -> PublishResponse:
    """Use the official YouTube Data API — kept for users who set OAuth."""
    result = await upload_video_to_youtube(
        video_path=clip['file_path'],
        title=request.title,
        description=request.description,
        tags=request.tags,
        privacy_status=request.privacy_status,
    )

    if result['status'] == 'success':
        await save_publish_log({
            'clip_id': request.clip_id,
            'platform': 'youtube',
            'youtube_url': result['youtube_url'],
            'method': 'official',
        })

    return PublishResponse(
        youtube_url=result.get('youtube_url'),
        status=result['status'],
        message=result['message'],
    )


def _absolute_clip_path(file_path: str) -> Path:
    """Resolve a stored `clip.file_path` to an absolute file."""
    p = Path(file_path)
    if p.is_absolute():
        return p
    # Relative paths are stored relative to WORKSPACE_DIR (OUTPUT_DIR lives there).
    return WORKSPACE_DIR / p


@router.get("/export/{clip_id}/path")
async def get_export_path(clip_id: str):
    """Get local file path for manual export."""
    clip = await get_clip(clip_id)
    
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    return {
        'clip_id': clip_id,
        'file_path': clip['file_path'],
        'message': 'Use this path to manually upload to other platforms'
    }


@router.get("/open-folder")
async def open_output_folder():
    """Open the output folder in system file manager."""
    folder = str(OUTPUT_DIR)
    try:
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', folder])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', folder])
        else:  # Linux
            subprocess.Popen(['xdg-open', folder])
        return {'status': 'opened', 'path': folder}
    except Exception as e:
        # Return the path even if we can't open it (e.g., headless server)
        return {'status': 'path_only', 'path': folder, 'message': str(e)}
