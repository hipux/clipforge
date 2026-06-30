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
    min_duration: int = 30  # seconds
    max_duration: int = 90  # seconds
    max_moments: int = 15
    user_instructions: str = ""  # optional LLM instructions
    preset_id: str = "default"  # content preset (#4): default | youtube_cuts | films_anime | streams


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
    score: Optional["ScoreBreakdown"] = None  # virality/hook/reason; set at processing time
                                          # forward ref; resolved by model_rebuild()
                                          # further down the file.


class ScoreBreakdown(BaseModel):
    """Sub-score breakdown explaining why a clip went viral.

    Surfaced on the Publish page so the operator can sanity-check the AI's
    pick before publishing. Multi-dimensional on purpose — a single number
    hides which signal (hook / self-containment / pacing) drove it.
    """
    overall: int = Field(..., ge=0, le=100,
                        description="Aggregated virality score (0-100)")
    hook: float = Field(0.0, ge=0, le=1,
                       description="Hook strength (0-1) — does the clip grab attention?")
    self_contained: float = Field(0.0, ge=0, le=1,
                                  description="Self-containment (0-1) — works without context?")
    pacing: float = Field(0.0, ge=0, le=1,
                          description="Audio/visual energy (0-1) — YamNet + motion")
    content_type: str = Field("",
                              description="Hook | Explanation | Funny | Story | Action | Music")
    content_emoji: str = Field("", description="Emoji marker matching content_type")
    reason: str = Field("", description="One-line verdict from the LLM")
    speakers: List[str] = Field(default_factory=list,
                                description="Person A/B/C labels from cross-modal analysis")


# Publishing models
class PublishRequest(BaseModel):
    clip_id: str
    title: str
    description: str = ""
    tags: List[str] = []
    privacy_status: str = "public"  # public, unlisted, private
    method: str = "browser"         # "browser" (ytb-up) OR "official" (OAuth API)
    account_id: Optional[str] = None  # future: pick from #5 multi-account roster
    cookies_path: Optional[str] = None  # browser-method override (path to .json)


# ─── Multi-account (#5) ────────────────────────────────────────────────────

class Account(BaseModel):
    """One publishing identity (a YouTube channel today, TikTok later)."""
    id: str
    name: str
    platform: str = "youtube"
    cookies_path: Optional[str] = None
    proxy: Optional[str] = None           # NULL = no proxy (proxy step deferred by user)
    preferred_preset: str = "default"     # content preset id
    last_used_at: Optional[str] = None    # ISO timestamp; set on publish
    created_at: Optional[str] = None


class AccountCreate(BaseModel):
    """Payload for POST /api/accounts — `id` is auto-generated if omitted."""
    name: str
    platform: str = "youtube"
    cookies_path: Optional[str] = None
    proxy: Optional[str] = None
    preferred_preset: str = "default"


class AccountUpdate(BaseModel):
    """PATCH-style partial updates (any field optional)."""
    name: Optional[str] = None
    platform: Optional[str] = None
    cookies_path: Optional[str] = None
    proxy: Optional[str] = None
    preferred_preset: Optional[str] = None


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

# ─── GPU Pipeline Extensions ───────────────────────────────────────────────

class GPUStatus(BaseModel):
    """GPU status for frontend monitoring."""
    device: str  # "cuda" or "cpu"
    is_gpu: bool
    vram_usage: dict  # {allocated_gb, reserved_gb, total_gb, free_gb}
    nvenc_available: bool = False
    loaded_models: List[str] = []


# Extended MomentCandidate for GPU pipeline (backward compatible)
# All new fields have defaults for backward compatibility with existing DB records
class MomentCandidateGPU(MomentCandidate):
    """Extended moment candidate with GPU pipeline metadata."""
    hook: Optional[str] = None
    virality_score: Optional[float] = None
    content_type: Optional[str] = None
    subtitle_mode: Optional[str] = "ru_only"
    translated_text: Optional[str] = None
    camera_plan: Optional[str] = None  # JSON string of camera keyframes
    reasoning: Optional[str] = None
    pipeline_mode: str = "gpu"  # "gpu" or "legacy"


# Extended DetectMomentsRequest for GPU pipeline
class DetectMomentsRequestGPU(DetectMomentsRequest):
    """Extended detection request with user instructions for LLM."""
    user_instructions: str = ""
    pipeline_mode: str = "auto"  # "auto", "gpu", or "legacy"


# Resolve forward refs NOW so Pydantic v2 doesn't complain at import time
# (ScoreBreakdown is declared AFTER ProcessedClip — the field type is a real
# str-typed forward ref until we call model_rebuild()).
ProcessedClip.model_rebuild()
