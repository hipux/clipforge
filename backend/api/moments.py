"""Moments detection and management API."""
import logging
import uuid
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List
from backend.models import DetectMomentsRequest, MomentCandidate, UpdateMomentRequest, MomentCandidateGPU
from backend.services.detection_pipeline import detection_pipeline
from backend.db import get_video, save_moments, get_moments, update_moment

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active detection jobs
detection_jobs = {}


@router.post("/moments/detect")
async def start_moment_detection(request: DetectMomentsRequest):
    """Start moment detection for a video."""
    # Verify video exists
    video = await get_video(request.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if moments already exist
    existing_moments = await get_moments(request.video_id)
    if existing_moments:
        # Convert to API format
        moments = [
            {
                'id': m['id'],
                'video_id': m['video_id'],
                'start': m['start_time'],
                'end': m['end_time'],
                'score': m['score'],
                'reason': m['reason'] or '',
                'thumbnail_url': m['thumbnail_url'] or '',
                'approved': bool(m['approved'])
            }
            for m in existing_moments
        ]
        return {'job_id': 'existing', 'moments': moments, 'status': 'completed'}
    
    job_id = str(uuid.uuid4())
    
    detection_jobs[job_id] = {
        'status': 'pending',
        'video_id': request.video_id,
        'moments': None,
        'error': None,
    }
    
    # Start detection in background
    asyncio.create_task(run_moment_detection(job_id, video, request.min_duration, request.max_duration, request.max_moments))
    
    return {'job_id': job_id, 'status': 'pending'}


async def run_moment_detection(job_id: str, video: dict, min_duration: int = 30, max_duration: int = 90, max_moments: int = 15):
    """Run moment detection in background using GPU pipeline."""
    try:
        detection_jobs[job_id]['status'] = 'analyzing'
        detection_jobs[job_id]['progress'] = 0.0
        detection_jobs[job_id]['message'] = 'Starting GPU pipeline...'
        
        # Progress callback to update WebSocket clients
        async def progress_cb(data: dict):
            stage = data.get('stage', '')
            step = data.get('step', '')
            progress = data.get('progress', 0.0)
            
            detection_jobs[job_id]['progress'] = progress
            detection_jobs[job_id]['message'] = f"Stage {stage}: {step}..."
        
        # Run GPU pipeline (handles GPU vs CPU fallback internally)
        director_output = await detection_pipeline.run(
            video_path=video['file_path'],
            user_instructions="",
            max_moments=max_moments,
            min_duration=min_duration,
            max_duration=max_duration,
            progress_callback=progress_cb,
        )
        
        # Convert DirectorOutput to MomentCandidate format for database
        moments = []
        for instr in director_output.moments:
            moment = MomentCandidateGPU(
                id=str(uuid.uuid4()),
                video_id=video['id'],
                start=instr.start,
                end=instr.end,
                score=instr.virality_score / 100.0,
                reason=instr.reasoning or instr.hook,
                thumbnail_url="",  # Will be generated later
                approved=False,
                hook=instr.hook,
                virality_score=instr.virality_score,
                content_type=instr.content_type,
                subtitle_mode=instr.subtitle_mode.value,
                translated_text=None,
                camera_plan=json.dumps([kf.model_dump() for kf in instr.camera_plan]),
                reasoning=instr.reasoning,
                pipeline_mode="gpu",
            )
            moments.append(moment)
        
        # Save to database
        await save_moments([m.model_dump() for m in moments])
        
        detection_jobs[job_id]['status'] = 'completed'
        detection_jobs[job_id]['moments'] = [m.model_dump() for m in moments]
        detection_jobs[job_id]['progress'] = 1.0
        detection_jobs[job_id]['message'] = f'Found {len(moments)} viral moments'
    
    except Exception as e:
        import traceback
        logger.error(f"Moment detection error: {e}")
        logger.error(traceback.format_exc())
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
