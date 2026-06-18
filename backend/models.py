"""Pydantic models for ClipForge API."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Download models
class DownloadRequest(BaseModel):
    url: str = Field(..., description="Video URL from YouTube, Rutube, or VK Video")


class DownloadResponse(BaseModel):
    job_id: str
    status: str


class VideoInfo(BaseModel):
    id: str
    title: str
    duration: float
    thumbnail_url: str
    file_path: str
    platform: str


# Moment detection models
class MomentCandidate(BaseModel):
    id: str
    video_id: str
    start: float
    end: float
    score: float
    reason: str
    thumbnail_url: str
    approved: bool = False


class DetectMomentsRequest(BaseModel):
    video_id: str


class UpdateMomentRequest(BaseModel):
    approved: Optional[bool] = None
    start: Optional[float] = None
    end: Optional[float] = None


# Processing models
class BannerSettings(BaseModel):
    enabled: bool = False
    banner_id: Optional[str] = None
    url: Optional[str] = None
    position: str = "top-right"  # top-left, top-right, bottom-left, bottom-right, top-center, bottom-center
    size: int = 20  # percentage of video width
    opacity: int = 80  # 0-100


class EffectSettings(BaseModel):
    subtitles: bool = False
    blur_background: bool = False
    mirror: bool = False
    color_correction: bool = False
    subtitle_style: str = "karaoke"  # classic, karaoke, box, outlined, minimal
    banner: Optional[BannerSettings] = None


class ProcessRequest(BaseModel):
    moment_ids: List[str]
    effects: EffectSettings


class ProcessedClip(BaseModel):
    id: str
    moment_id: str
    file_path: str
    status: str
    effects: EffectSettings


# Publishing models
class PublishRequest(BaseModel):
    clip_id: str
    title: str
    description: str = ""
    tags: List[str] = []
    privacy_status: str = "public"  # public, unlisted, private


class PublishResponse(BaseModel):
    youtube_url: Optional[str] = None
    status: str
    message: str


# WebSocket progress models
class ProgressMessage(BaseModel):
    job_id: str
    status: str  # running, completed, error
    progress: float  # 0.0 to 1.0
    current_step: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict] = None


# YouTube auth models
class YouTubeAuthStatus(BaseModel):
    authenticated: bool
    auth_url: Optional[str] = None
