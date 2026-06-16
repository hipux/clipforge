"""Publishing API endpoints for YouTube."""
from fastapi import APIRouter, HTTPException
from backend.models import PublishRequest, PublishResponse, YouTubeAuthStatus
from backend.services.youtube_publisher import (
    upload_video_to_youtube,
    initiate_oauth_flow,
    complete_oauth_flow,
    is_authenticated
)
from backend.db import get_clip, save_publish_log

router = APIRouter()


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
    """Upload a clip to YouTube Shorts."""
    # Get clip from database
    clip = await get_clip(request.clip_id)
    
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    # Upload to YouTube
    result = await upload_video_to_youtube(
        video_path=clip['file_path'],
        title=request.title,
        description=request.description,
        tags=request.tags,
        privacy_status=request.privacy_status,
    )
    
    # Save publish log
    if result['status'] == 'success':
        await save_publish_log({
            'clip_id': request.clip_id,
            'platform': 'youtube',
            'youtube_url': result['youtube_url'],
        })
    
    return PublishResponse(
        youtube_url=result.get('youtube_url'),
        status=result['status'],
        message=result['message']
    )


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
