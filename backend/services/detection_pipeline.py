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

        import time
        from pathlib import Path
        
        start_time = time.time()
        video_name = Path(video_path).name
        
        # Get video info for estimates
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps
        cap.release()
        
        video_duration_min = video_duration / 60.0
        
        # Time estimates for RTX 5060
        if video_duration_min <= 30:
            est_stage1 = "2-3мин"
            est_stage2 = "1-2мин"
            est_total = "3-5 минут"
        elif video_duration_min <= 60:
            est_stage1 = "4-6мин"
            est_stage2 = "2-3мин"
            est_total = "6-9 минут"
        else:
            est_stage1 = "8-12мин"
            est_stage2 = "3-4мин"
            est_total = "11-16 минут"
        
        gpu_mode = "GPU (CUDA)" if vram_manager.is_gpu else "CPU (резервный)"
        logger.info(f"🚀 [Детекция] Запуск GPU-пайплайна для видео: {video_name} ({video_duration_min:.1f} мин)")
        logger.info(f"📊 [Детекция] Режим: {gpu_mode}")
        logger.info(f"⏱️  [Детекция] Примерное время: ~{est_total} (Этап 1: {est_stage1} + Этап 2: {est_stage2})")
        logger.info("")

        # ─── STAGE 1: Data Collection ────────────────────────────────────────
        stage1_start = time.time()
        logger.info("▶️  [Этап 1/3] Начало сбора данных...")
        logger.info("")
        
        if progress_callback:
            await progress_callback({"stage": 1, "step": "transcription", "progress": 0.05})

        transcript = whisper_gpu.transcribe(video_path)
        vram_manager.unload_all()  # Safety flush

        if progress_callback:
            await progress_callback({"stage": 1, "step": "face_detection", "progress": 0.30})

        face_timeline = face_detector.detect_faces_timeline(video_path)
        vram_manager.unload_all()  # Safety flush

        if progress_callback:
            await progress_callback({"stage": 1, "step": "audio_analysis", "progress": 0.50})

        audio_analysis = audio_analyzer.analyze(video_path)
        
        stage1_time = time.time() - stage1_start
        logger.info("")
        logger.info(f"✅  [Этап 1/3] Завершён за {stage1_time:.1f}с")
        logger.info("")

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
        stage2_start = time.time()
        logger.info("▶️  [Этап 2/3] Начало ИИ-анализа...")
        logger.info("")
        
        if progress_callback:
            await progress_callback({"stage": 2, "step": "context_building", "progress": 0.65})

        # Build context chunks (dynamic based on video duration)
        context_chunks = context_builder.build_chunks(ctx, user_instructions)
        
        # Estimate total LLM time based on number of chunks
        chunk_analyze_time = 30  # ~30s per chunk estimate for RTX 5060
        est_llm_time = len(context_chunks) * chunk_analyze_time
        if len(context_chunks) > 1:
            est_llm_time += 20  # +20s for consolidation pass
        
        logger.info(f"🧠 [LLM] Ожидаемое время анализа: ~{est_llm_time}с ({len(context_chunks)} чанков)")

        if progress_callback:
            await progress_callback({"stage": 2, "step": "llm_analysis", "progress": 0.70})

        director_output = llm_director.analyze(context_chunks, user_instructions)
        vram_manager.unload_all()  # Safety flush
        
        stage2_time = time.time() - stage2_start
        logger.info("")
        logger.info(f"✅  [Этап 2/3] Завершён за {stage2_time:.1f}с")
        logger.info("")

        if progress_callback:
            await progress_callback({"stage": 2, "step": "done", "progress": 0.90})

        # ─── STAGE 3: Done (rendering happens per-clip via /render endpoint) ─
        logger.info("▶️  [Этап 3/3] Подготовка результатов...")
        logger.info("")
        
        if progress_callback:
            await progress_callback({"stage": 3, "step": "done", "progress": 1.0})

        total_time = time.time() - start_time
        logger.info(f"✅  [Этап 3/3] Завершён за 0.5с")
        logger.info("")
        logger.info("="*60)
        logger.info(f"🎉 [Детекция] Готово! Найдено {len(director_output.moments)} моментов за {total_time:.1f}с")
        
        # Log top moments
        if director_output.moments:
            top_moment = director_output.moments[0]
            logger.info(f"🏆 Топ момент: \"{top_moment.hook}\" (вирусность: {top_moment.virality_score:.0f}/100)")
        
        logger.info("="*60)
        logger.info("")
        
        return director_output


# Global singleton instance
detection_pipeline = DetectionPipeline()
