"""GPU Pipeline API endpoints - extends moments.py with GPU functionality."""
import logging
import json
from fastapi import APIRouter, HTTPException
from backend.models import GPUStatus
from backend.services.vram_manager import vram_manager
from backend.services.gpu_renderer import HAS_NVENC

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gpu/status", response_model=GPUStatus)
async def get_gpu_status():
    """Get current GPU status and VRAM usage.
    
    Returns:
        GPUStatus with device info, VRAM usage, and loaded models
    """
    return GPUStatus(
        device=vram_manager.device,
        is_gpu=vram_manager.is_gpu,
        vram_usage=vram_manager.get_vram_usage(),
        nvenc_available=HAS_NVENC,
        loaded_models=vram_manager.get_loaded_models(),
    )
