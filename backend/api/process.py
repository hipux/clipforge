"""Video processing API endpoints."""
import logging
import uuid
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List
from backend.models import ProcessRequest, ProcessedClip
from backend.services.video_processor import process_moment_clip
from backend.db import get_video, get_moments, save_clip, get_clips, get_clip

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active processing jobs
processing_jobs = {}


@router.post("/process")
async def start_processing(request: ProcessRequest):
    """Start processing selected moments with effects."""
    job_id = str(uuid.uuid4())
    
    # Verify moments exist
    moments_data = []
    for moment_id in request.moment_ids:
        # Get moment from database
        from backend.db import get_db
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM moments WHERE id = ?", (moment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    moment_dict = dict(row)
                    # Convert database field names to API field names
                    moment_dict['start'] = moment_dict['start_time']
                    moment_dict['end'] = moment_dict['end_time']
                    moments_data.append(moment_dict)
    
    if not moments_data:
        raise HTTPException(status_code=404, detail="No valid moments found")
    
    processing_jobs[job_id] = {
        'status': 'pending',
        'moments': moments_data,
        'effects': request.effects,
        'clips': [],
        'current_clip': 0,
        'total_clips': len(moments_data),
        'error': None,
    }
    
    # Start processing in background
    asyncio.create_task(run_processing(job_id))
    
    return {
        'job_id': job_id,
        'status': 'pending',
        'total_clips': len(moments_data)
    }


async def run_processing(job_id: str):
    """Run video processing in background."""
    try:
        job = processing_jobs[job_id]
        moments = job['moments']
        effects = job['effects']
        
        job['status'] = 'processing'
        
        # Get source video path (from first moment)
        first_moment_video_id = moments[0]['video_id']
        video = await get_video(first_moment_video_id)
        
        if not video:
            raise Exception("Source video not found")
        
        source_video_path = video['file_path']
        
        # Process each moment
        for idx, moment in enumerate(moments):
            job['current_clip'] = idx + 1
            job['current_moment_id'] = moment['id']
            job['message'] = f"Processing clip {idx + 1} of {len(moments)}"
            # Reset clip progress to 0 when starting a new clip
            job['clip_progress'] = 0.0
            job['clip_message'] = 'Starting...'
            
            def progress_callback(progress: float, message: str):
                job['clip_progress'] = progress
                job['clip_message'] = message
            
            # Process the clip
            clip_data = await process_moment_clip(
                source_video_path,
                moment,
                effects,
                progress_callback=progress_callback
            )
            
            if clip_data:
                # Save to database
                await save_clip({
                    **clip_data,
                    'effects_json': effects.model_dump_json(),
                })
                job['clips'].append(clip_data)
            else:
                logger.warning(f"Failed to process moment {moment['id']}")
        
        job['status'] = 'completed'
        job['message'] = f"Successfully processed {len(job['clips'])} clips"
    
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"Processing error: {error_detail}")
        processing_jobs[job_id]['status'] = 'error'
        processing_jobs[job_id]['error'] = str(e)
        processing_jobs[job_id]['message'] = f"Error: {str(e)}"


@router.websocket("/ws/process/{job_id}")
async def processing_websocket(websocket: WebSocket, job_id: str):
    """WebSocket for processing progress."""
    await websocket.accept()
    
    try:
        # Wait a moment for job to be created if it's not ready yet
        max_retries = 10
        retry_count = 0
        while job_id not in processing_jobs and retry_count < max_retries:
            await asyncio.sleep(0.1)
            retry_count += 1
        
        while True:
            job = processing_jobs.get(job_id)
            
            if not job:
                await websocket.send_json({
                    'status': 'error',
                    'message': 'Job not found'
                })
                break
            
            message = {
                'status': job['status'],
                'current_clip': job.get('current_clip', 0),
                'total_clips': job['total_clips'],
                'message': job.get('message', ''),
                'clip_progress': job.get('clip_progress', 0.0),
                'clip_message': job.get('clip_message', ''),
            }
            
            if job['status'] == 'completed':
                message['clips'] = job['clips']
                await websocket.send_json(message)
                break
            
            elif job['status'] == 'error':
                message['error'] = job.get('error', 'Unknown error')
                logger.error(f"Processing job {job_id} failed: {message['error']}")
                await websocket.send_json(message)
                # Wait to ensure client receives error before closing
                await asyncio.sleep(0.5)
                break
            
            else:
                await websocket.send_json(message)
            
            await asyncio.sleep(0.3)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        try:
            await websocket.send_json({
                'status': 'error',
                'error': str(e),
                'message': f'WebSocket error: {str(e)}'
            })
        except:
            pass


@router.get("/clips", response_model=List[ProcessedClip])
async def list_clips():
    """Get all processed clips."""
    clips = await get_clips()
    
    return [
        ProcessedClip(
            id=c['id'],
            moment_id=c['moment_id'],
            file_path=c['file_path'],
            status=c['status'],
            effects=json.loads(c['effects_json']) if c.get('effects_json') else {}
        )
        for c in clips
    ]


@router.get("/clips/{clip_id}")
async def get_clip_endpoint(clip_id: str):
    """Get a single clip."""
    clip = await get_clip(clip_id)
    
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    return ProcessedClip(
        id=clip['id'],
        moment_id=clip['moment_id'],
        file_path=clip['file_path'],
        status=clip['status'],
        effects=json.loads(clip['effects_json']) if clip.get('effects_json') else {}
    )
