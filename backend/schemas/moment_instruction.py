"""Pydantic schemas for GPU pipeline moment detection and LLM director."""
from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class SubtitleMode(str, Enum):
    """Subtitle rendering mode for multilingual content."""
    ru_only = "ru_only"
    en_only = "en_only"
    dual = "dual"
    original = "original"


class CameraKeyframe(BaseModel):
    """Camera movement keyframe for dynamic crop tracking."""
    time: float = Field(0.0, description="seconds relative to moment start")
    target_face_id: Optional[int] = Field(None, description="face track_id, None = center frame")
    crop_center_x: float = Field(0.5, ge=0.0, le=1.0, description="horizontal crop center (0.0-1.0)")
    crop_center_y: float = Field(0.5, ge=0.0, le=1.0, description="vertical crop center (0.0-1.0)")
    transition: str = Field("smooth", description="'cut' or 'smooth'")


class MomentInstruction(BaseModel):
    """LLM-generated moment instruction with virality analysis and camera plan."""
    start: float = Field(description="absolute second in video")
    end: float = Field(description="absolute second in video")
    hook: str = Field(description="what grabs attention in first 3 seconds")
    virality_score: float = Field(default=50, ge=0, le=100, description="viral potential score")
    content_type: str = Field(default="explanation", description="reaction|explanation|story|joke|argument")
    subtitle_mode: SubtitleMode = SubtitleMode.ru_only
    translated_text: Optional[str] = Field(None, description="Russian translation if original is not Russian")
    camera_plan: List[CameraKeyframe] = Field(default_factory=list, description="camera movement keyframes")
    reasoning: str = Field(default="", description="why this moment is viral")


class DirectorOutput(BaseModel):
    """LLM director output with ranked moments."""
    moments: List[MomentInstruction] = Field(description="top viral moments, best first")
    total_analyzed: int = Field(default=0, description="total candidate moments analyzed")
    language_detected: str = Field(default="unknown", description="primary language detected")


# ─── Stage 1: Data Collection Schemas ──────────────────────────────────────


class TranscriptWord(BaseModel):
    """Word-level timestamp from Whisper."""
    word: str
    start: float
    end: float
    probability: float


class TranscriptSegment(BaseModel):
    """Transcript segment with language detection."""
    text: str
    start: float
    end: float
    language: str
    words: List[TranscriptWord] = Field(default_factory=list)


class FaceDetection(BaseModel):
    """Face detection result with tracking ID."""
    bbox: List[float] = Field(description="[x1, y1, x2, y2] normalized 0..1")
    confidence: float
    track_id: Optional[int] = None


class FaceFrame(BaseModel):
    """Face detections at a specific timestamp."""
    timestamp: float
    faces: List[FaceDetection]


class FaceTimeline(BaseModel):
    """Complete face tracking timeline."""
    frames: List[FaceFrame]
    unique_face_ids: List[int]




class FacePresenceSegment(BaseModel):
    """Temporal segment when faces are visible in frame.
    
    More meaningful than counting unique IDs (which explodes due to tracker drift).
    Shows when the video actually has people in frame.
    """
    start: float = Field(description="segment start time (seconds)")
    end: float = Field(description="segment end time (seconds)")
    avg_face_count: float = Field(description="average number of faces in this segment")


class AudioPeak(BaseModel):
    """Audio energy peak (emotional spike)."""
    timestamp: float
    magnitude: float
    peak_type: str = Field(description="spike or sustained")


class AudioEvent(BaseModel):
    """Semantic audio event from YamNet (laughter, applause, cheering, music...).

    Unlike AudioPeak (raw energy), this says WHAT happened, which is a much
    stronger virality signal and is fed both to the LLM context and the
    deterministic scorer.
    """
    timestamp: float = Field(description="event center time (seconds)")
    label: str = Field(description="AudioSet class name, e.g. 'Laughter'")
    score: float = Field(description="classifier confidence 0..1")


class AudioAnalysis(BaseModel):
    """Audio analysis result."""
    peaks: List[AudioPeak]
    rms_timeline: List[dict] = Field(description="[{time, rms}]")
    avg_rms: float
    max_rms: float
    events: List[AudioEvent] = Field(default_factory=list, description="YamNet audio events")


class Stage1Context(BaseModel):
    """Assembled Stage 1 data for LLM consumption."""
    transcript: List[TranscriptSegment]
    face_timeline: FaceTimeline
    audio_analysis: AudioAnalysis
    video_duration: float
    video_path: str