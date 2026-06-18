"""File upload API for ClipForge."""
import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from backend.config import BANNERS_DIR

logger = logging.getLogger(__name__)

router = APIRouter()


class BannerUploadResponse(BaseModel):
    banner_id: str
    url: str


@router.post("/upload/banner", response_model=BannerUploadResponse)
async def upload_banner(file: UploadFile = File(...)):
    """
    Upload a banner/watermark image.
    
    Accepts PNG, WebP, JPG. Max 5MB.
    Returns banner_id and URL for previewing.
    """
    # Validate file type
    allowed_types = ["image/png", "image/webp", "image/jpeg", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: PNG, WebP, JPEG. Got: {file.content_type}"
        )
    
    # Read file
    contents = await file.read()
    
    # Validate size (5MB)
    max_size = 5 * 1024 * 1024
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max 5MB. Got: {len(contents) / 1024 / 1024:.2f}MB"
        )
    
    # Generate unique ID and save
    banner_id = str(uuid.uuid4())
    extension = Path(file.filename).suffix if file.filename else ".png"
    banner_path = BANNERS_DIR / f"{banner_id}{extension}"
    
    with open(banner_path, "wb") as f:
        f.write(contents)
    
    logger.info(f"Banner uploaded: {banner_id}{extension} ({len(contents)} bytes)")
    
    # Return URL (relative path for frontend)
    url = f"/files/banners/{banner_id}{extension}"
    
    return BannerUploadResponse(banner_id=banner_id, url=url)
