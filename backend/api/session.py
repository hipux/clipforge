"""Session persistence API for ClipForge."""
import logging
from fastapi import APIRouter, HTTPException
from backend.db import get_latest_video, get_moments_by_video, get_clips_by_video
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionState(BaseModel):
    """Current session state."""
    step: int  # 1=download, 2=moments, 3=effects, 4=process, 5=publish
    video_id: Optional[str] = None
    moments_count: int = 0
    selected_moments_count: int = 0
    processed_clips_count: int = 0


@router.get("/session/current", response_model=SessionState)
async def get_current_session():
    """
    Retrieve the current session state for resuming work.
    
    Returns the last video, detected moments, and processed clips
    to allow the user to continue from where they left off.
    """
    try:
        # Get the most recent video
        video = await get_latest_video()
        
        if not video:
            # No session to resume
            return SessionState(step=1)
        
        video_id = video["id"]
        
        # Get moments for this video
        moments = await get_moments_by_video(video_id)
        approved_moments = [m for m in moments if m.get("approved")]
        
        # Get processed clips
        clips = await get_clips_by_video(video_id)
        completed_clips = [c for c in clips if c.get("status") == "completed"]
        
        # Determine current step based on what exists
        if completed_clips:
            # Has completed clips → step 5 (publish)
            step = 5
        elif approved_moments:
            # Has approved moments but no clips → step 4 (process)
            step = 4
        elif moments:
            # Has detected moments but none approved → step 2 or 3
            # If some moments exist, assume user was reviewing/configuring
            step = 3
        else:
            # Has video but no moments → step 2 (detect moments)
            step = 2
        
        return SessionState(
            step=step,
            video_id=video_id,
            moments_count=len(moments),
            selected_moments_count=len(approved_moments),
            processed_clips_count=len(completed_clips),
        )
    
    except Exception as e:
        logger.error(f"Error retrieving session state: {e}")
        # On error, return fresh session
        return SessionState(step=1)
