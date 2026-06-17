"""
WebSocket-only router for ClipForge.

Mounted WITHOUT /api prefix so paths are:
  /ws/download/{job_id}
  /ws/moments/{job_id}
  /ws/process/{job_id}

These match what the Vite proxy forwards to port 8000.
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import job dictionaries from the API modules
from backend.api.download import download_jobs
from backend.api.moments import detection_jobs
from backend.api.process import processing_jobs

ws_router = APIRouter()


@ws_router.websocket("/ws/download/{job_id}")
async def ws_download_progress(websocket: WebSocket, job_id: str):
    """Real-time download progress via WebSocket."""
    await websocket.accept()
    try:
        while True:
            job = download_jobs.get(job_id)
            if not job:
                await websocket.send_json({"status": "error", "message": "Job not found"})
                break

            message = {"status": job["status"], "progress": job.get("progress", {})}

            if job["status"] == "completed":
                message["video"] = job["video_info"].model_dump() if job.get("video_info") else None
                await websocket.send_json(message)
                break
            elif job["status"] == "error":
                message["error"] = job.get("error", "Unknown error")
                await websocket.send_json(message)
                break
            else:
                await websocket.send_json(message)

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass


@ws_router.websocket("/ws/moments/{job_id}")
async def ws_moments_progress(websocket: WebSocket, job_id: str):
    """Real-time moment detection progress via WebSocket."""
    await websocket.accept()
    try:
        while True:
            job = detection_jobs.get(job_id)
            if not job:
                await websocket.send_json({"status": "error", "message": "Job not found"})
                break

            message = {
                "status": job["status"],
                "progress": job.get("progress", 0),
                "message": job.get("message", ""),
            }

            if job["status"] == "completed":
                message["moments"] = job.get("moments", [])
                await websocket.send_json(message)
                break
            elif job["status"] == "error":
                message["error"] = job.get("error", "Unknown error")
                await websocket.send_json(message)
                break
            else:
                await websocket.send_json(message)

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass


@ws_router.websocket("/ws/process/{job_id}")
async def ws_process_progress(websocket: WebSocket, job_id: str):
    """Real-time processing progress via WebSocket."""
    await websocket.accept()
    try:
        while True:
            job = processing_jobs.get(job_id)
            if not job:
                await websocket.send_json({"status": "error", "message": "Job not found"})
                break

            message = {
                "status": job["status"],
                "current_clip": job.get("current_clip", 0),
                "total_clips": job.get("total_clips", 0),
                "message": job.get("message", ""),
                "clip_progress": job.get("clip_progress", 0.0),
                "clip_message": job.get("clip_message", ""),
            }

            if job["status"] == "completed":
                message["clips"] = job.get("clips", [])
                await websocket.send_json(message)
                break
            elif job["status"] == "error":
                message["error"] = job.get("error", "Unknown error")
                await websocket.send_json(message)
                break
            else:
                await websocket.send_json(message)

            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass
