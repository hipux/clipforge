"""Download API endpoints."""
import logging
import uuid
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from backend.models import DownloadRequest, DownloadResponse, VideoInfo
from backend.services.downloader import download_video
from backend.db import save_video

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active download jobs
download_jobs = {}


@router.post("/download", response_model=DownloadResponse)
async def start_download(request: DownloadRequest):
    """Start video download job."""
    job_id = str(uuid.uuid4())
    
    download_jobs[job_id] = {
        'status': 'pending',
        'url': request.url,
        'video_info': None,
        'error': None,
    }
    
    # Start download in background
    asyncio.create_task(run_download(job_id, request.url))
    
    return DownloadResponse(job_id=job_id, status='pending')


async def run_download(job_id: str, url: str):
    """Run download task in background."""
    try:
        download_jobs[job_id]['status'] = 'downloading'
        
        def progress_callback(progress_data):
            # Update job progress
            download_jobs[job_id]['progress'] = progress_data
        
        video_info = await download_video(url, progress_callback=progress_callback)
        
        # Save to database
        await save_video({
            'id': video_info.id,
            'url': url,
            'platform': video_info.platform,
            'title': video_info.title,
            'duration': video_info.duration,
            'thumbnail_url': video_info.thumbnail_url,
            'file_path': video_info.file_path,
        })
        
        download_jobs[job_id]['status'] = 'completed'
        download_jobs[job_id]['video_info'] = video_info
    
    except Exception as e:
        download_jobs[job_id]['status'] = 'error'
        download_jobs[job_id]['error'] = str(e)


@router.websocket("/ws/download/{job_id}")
async def download_progress_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for download progress updates."""
    await websocket.accept()
    
    try:
        while True:
            job = download_jobs.get(job_id)
            
            if not job:
                await websocket.send_json({
                    'status': 'error',
                    'message': 'Job not found'
                })
                break
            
            # Send current status
            message = {
                'status': job['status'],
                'progress': job.get('progress', {}),
            }
            
            if job['status'] == 'completed':
                message['video'] = job['video_info'].model_dump() if job['video_info'] else None
                await websocket.send_json(message)
                break
            
            elif job['status'] == 'error':
                message['error'] = job['error']
                await websocket.send_json(message)
                break
            
            else:
                await websocket.send_json(message)
            
            await asyncio.sleep(0.5)  # Update every 500ms
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@router.get("/download/{job_id}/status")
async def get_download_status(job_id: str):
    """Get download job status (REST alternative to WebSocket)."""
    job = download_jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    response = {
        'job_id': job_id,
        'status': job['status'],
    }
    
    if job['status'] == 'completed' and job['video_info']:
        response['video'] = job['video_info'].model_dump()
    elif job['status'] == 'error':
        response['error'] = job['error']
    elif 'progress' in job:
        response['progress'] = job['progress']
    
    return response
