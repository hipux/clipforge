"""Moments detection and management API."""
import logging
import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List
from backend.models import DetectMomentsRequest, MomentCandidate, UpdateMomentRequest
from backend.services.scene_detector import detect_moments_from_video
from backend.services.speech_scorer import analyze_speech_content
from backend.db import get_video, save_moments, get_moments, update_moment

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active detection jobs
detection_jobs = {}


@router.post("/moments/detect")
async def start_moment_detection(request: DetectMomentsRequest):
    """Start moment detection for a video."""
    job_id = str(uuid.uuid4())
    
    # Verify video exists
    video = await get_video(request.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    detection_jobs[job_id] = {
        'status': 'pending',
        'video_id': request.video_id,
        'moments': None,
        'error': None,
    }
    
    # Start detection in background
    asyncio.create_task(run_moment_detection(job_id, video))
    
    return {'job_id': job_id, 'status': 'pending'}


async def run_moment_detection(job_id: str, video: dict):
    """Run moment detection in background."""
    try:
        detection_jobs[job_id]['status'] = 'analyzing'
        detection_jobs[job_id]['progress'] = 0.1
        detection_jobs[job_id]['message'] = 'Analyzing speech content...'
        
        # Step 1: Analyze speech (optional, might fail if Whisper unavailable)
        speech_scores = await analyze_speech_content(video['file_path'])
        
        detection_jobs[job_id]['progress'] = 0.4
        detection_jobs[job_id]['message'] = 'Detecting scenes and audio energy...'
        
        # Step 2: Detect moments using combined analysis
        moments = await detect_moments_from_video(
            video['file_path'],
            video['id'],
            video['duration'],
            speech_scores=speech_scores
        )
        
        detection_jobs[job_id]['progress'] = 0.8
        detection_jobs[job_id]['message'] = 'Saving moments...'
        
        # Save to database
        await save_moments(moments)
        
        detection_jobs[job_id]['status'] = 'completed'
        detection_jobs[job_id]['moments'] = moments
        detection_jobs[job_id]['progress'] = 1.0
        detection_jobs[job_id]['message'] = f'Found {len(moments)} interesting moments'
    
    except Exception as e:
        logger.error(f"Moment detection error: {e}")
        detection_jobs[job_id]['status'] = 'error'
        detection_jobs[job_id]['error'] = str(e)


@router.websocket("/ws/moments/{job_id}")
async def moment_detection_websocket(websocket: WebSocket, job_id: str):
    """WebSocket for moment detection progress."""
    await websocket.accept()
    
    try:
        while True:
            job = detection_jobs.get(job_id)
            
            if not job:
                await websocket.send_json({
                    'status': 'error',
                    'message': 'Job not found'
                })
                break
            
            message = {
                'status': job['status'],
                'progress': job.get('progress', 0.0),
                'message': job.get('message', ''),
            }
            
            if job['status'] == 'completed':
                message['moments'] = job['moments']
                await websocket.send_json(message)
                break
            
            elif job['status'] == 'error':
                message['error'] = job['error']
                await websocket.send_json(message)
                break
            
            else:
                await websocket.send_json(message)
            
            await asyncio.sleep(0.5)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


@router.get("/moments/{video_id}", response_model=List[MomentCandidate])
async def get_video_moments(video_id: str):
    """Get all detected moments for a video."""
    moments = await get_moments(video_id)
    
    # Convert DB format to API format
    return [
        MomentCandidate(
            id=m['id'],
            video_id=m['video_id'],
            start=m['start_time'],
            end=m['end_time'],
            score=m['score'],
            reason=m['reason'] or '',
            thumbnail_url=m['thumbnail_url'] or '',
            approved=bool(m['approved'])
        )
        for m in moments
    ]


@router.put("/moments/{moment_id}")
async def update_moment_endpoint(moment_id: str, request: UpdateMomentRequest):
    """Update moment (approve, adjust timestamps)."""
    updates = {}
    
    if request.approved is not None:
        updates['approved'] = int(request.approved)
    if request.start is not None:
        updates['start_time'] = request.start
    if request.end is not None:
        updates['end_time'] = request.end
    
    if not updates:
        return {'message': 'No updates provided'}
    
    await update_moment(moment_id, updates)
    
    return {'message': 'Moment updated successfully'}


@router.delete("/moments/{moment_id}")
async def delete_moment(moment_id: str):
    """Delete a moment candidate."""
    # Simple implementation - just mark as not approved
    await update_moment(moment_id, {'approved': 0})
    return {'message': 'Moment deleted'}
