"""Publishing API endpoints for YouTube.

Two upload paths supported (chosen by `PublishRequest.method`):
    - "official" — Google's YouTube Data API v3, paid Workspace required.
      Kept for users who already have credentials configured.
    - "browser"  — `ytb-up` Playwright + Firefox cookies. The default — does
      not ping Google as an "official API client", so it won't trigger
      quota/automation flags for short-clip publishers.

Both paths return the same `PublishResponse` shape so the frontend doesn't
need to know which one ran.
"""
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
from backend.services.youtube_browser_publisher import upload_with_cookies
from backend.db import get_clip, save_publish_log, get_account, touch_account
from backend.config import OUTPUT_DIR, WORKSPACE_DIR

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
    """Use `ytb-up` Playwright + cookie auth. Default — looks like a real user.

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

    result = await upload_with_cookies(
        file_path=video_path,
        title=request.title,
        description=request.description,
        tags=request.tags,
        cookies_path=cookies_path,
        proxy=proxy,
    )

    if result.status == "success":
        await save_publish_log({
            'clip_id': request.clip_id,
            'platform': 'youtube',
            'youtube_url': result.youtube_url,
            'method': 'browser',
            'account_id': request.account_id,
        })
        if request.account_id:
            await touch_account(request.account_id)
    return PublishResponse(
        youtube_url=result.youtube_url,
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
