"""GPU detection pipeline orchestrator - coordinates 3-stage analysis.

Stage 1: Data Collection (Whisper + YOLO + Librosa)
Stage 2: LLM Director (Qwen2.5-7B)
Stage 3: Rendering (handled separately via API)
"""
from __future__ import annotations
import logging
import os
from typing import AsyncGenerator, Optional, Callable
from backend.services.vram_manager import vram_manager
from backend.services.whisper_gpu import whisper_gpu
from backend.services.face_detector import face_detector
from backend.services.audio_analyzer import audio_analyzer
from backend.services.context_builder import context_builder
from backend.services.llm_director import llm_director
from backend.schemas.moment_instruction import Stage1Context, DirectorOutput

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Orchestrates 3-stage GPU pipeline for moment detection.
    
    GPU-first: uses GPU when CUDA available, falls back to legacy CPU pipeline otherwise.
    """

    def _should_use_gpu(self) -> bool:
        """Determine if GPU pipeline should be used.
        
        Returns:
            True if GPU should be used, False for CPU legacy fallback
        """
        from backend.gpu_config import USE_GPU_PIPELINE
        
        cfg = USE_GPU_PIPELINE.lower()
        if cfg == "false":
            return False
        # "true" or "auto" both use GPU if CUDA available
        return vram_manager.is_gpu

    async def run(
        self,
        video_path: str,
        user_instructions: str = "",
        max_moments: int = 10,
        min_duration: int = 30,
        max_duration: int = 90,
        progress_callback: Optional[Callable] = None,
    ) -> DirectorOutput:
        """Run 3-stage GPU pipeline for moment detection.
        
        Args:
            video_path: Path to video file
            user_instructions: Optional user analysis instructions
            max_moments: Maximum number of moments to return
            min_duration: Minimum moment duration in seconds
            max_duration: Maximum moment duration in seconds
            progress_callback: Optional async callback for progress updates
            
        Returns:
            DirectorOutput with detected moments
        """
        use_gpu = self._should_use_gpu()

        if not use_gpu:
            logger.warning("GPU not available — using legacy CPU pipeline")
            # Import legacy pipeline only when needed
            from backend.services.scene_detector import detect_moments_from_video
            from backend.services.speech_scorer import analyze_speech_content
            
            # Legacy CPU pipeline (existing code path)
            if progress_callback:
                await progress_callback({"stage": "legacy", "step": "analyzing", "progress": 0.5})
            
            speech_scores = analyze_speech_content(video_path)
            
            # Get video duration
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_duration = total_frames / fps
            cap.release()
            
            # Legacy detection returns moments in old format
            # We need to wrap it in DirectorOutput for API compatibility
            legacy_moments = detect_moments_from_video(
                video_path,
                "temp_id",
                video_duration,
                speech_scores,
                max_moments,
                min_duration,
                max_duration
            )
            
            # Convert to DirectorOutput format (simplified, no LLM analysis)
            from backend.schemas.moment_instruction import MomentInstruction, SubtitleMode
            moments = []
            for m in legacy_moments:
                moments.append(MomentInstruction(
                    start=m.start,
                    end=m.end,
                    hook="Interesting moment detected",
                    virality_score=m.score * 100,
                    content_type="explanation",
                    subtitle_mode=SubtitleMode.ru_only,
                    reasoning=m.reason or "CPU legacy detection",
                    camera_plan=[],
                ))
            
            return DirectorOutput(
                moments=moments,
                total_analyzed=len(moments),
                language_detected="unknown"
            )

        logger.info(f"Starting 3-stage GPU pipeline: {video_path}")

        # ─── STAGE 1: Data Collection ────────────────────────────────────────
        if progress_callback:
            await progress_callback({"stage": 1, "step": "transcription", "progress": 0.05})

        logger.info("Stage 1a: Transcribing audio with Whisper GPU...")
        transcript = whisper_gpu.transcribe(video_path)
        vram_manager.unload_all()  # Safety flush

        if progress_callback:
            await progress_callback({"stage": 1, "step": "face_detection", "progress": 0.30})

        logger.info("Stage 1b: Detecting faces with YOLOv8n...")
        face_timeline = face_detector.detect_faces_timeline(video_path)
        vram_manager.unload_all()  # Safety flush

        if progress_callback:
            await progress_callback({"stage": 1, "step": "audio_analysis", "progress": 0.50})

        logger.info("Stage 1c: Analyzing audio peaks...")
        audio_analysis = audio_analyzer.analyze(video_path)

        # Get video duration
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps
        cap.release()

        ctx = Stage1Context(
            transcript=transcript,
            face_timeline=face_timeline,
            audio_analysis=audio_analysis,
            video_duration=video_duration,
            video_path=video_path,
        )

        if progress_callback:
            await progress_callback({"stage": 1, "step": "done", "progress": 0.60})

        # ─── STAGE 2: LLM Director ───────────────────────────────────────────
        if progress_callback:
            await progress_callback({"stage": 2, "step": "context_building", "progress": 0.65})

        logger.info("Stage 2: Building context log...")
        context_log = context_builder.build_log(ctx, user_instructions)

        if progress_callback:
            await progress_callback({"stage": 2, "step": "llm_analysis", "progress": 0.70})

        logger.info("Stage 2: Sending to Qwen2.5-7B for analysis...")
        director_output = llm_director.analyze(context_log, user_instructions)
        vram_manager.unload_all()  # Safety flush

        if progress_callback:
            await progress_callback({"stage": 2, "step": "done", "progress": 0.90})

        # ─── STAGE 3: Done (rendering happens per-clip via /render endpoint) ─
        if progress_callback:
            await progress_callback({"stage": 3, "step": "done", "progress": 1.0})

        logger.info(f"Pipeline complete: {len(director_output.moments)} moments detected")
        return director_output


# Global singleton instance
detection_pipeline = DetectionPipeline()
