"""GPU detection pipeline orchestrator - coordinates 3-stage analysis.

Stage 1: Data Collection (Whisper + YOLO + Librosa)
Stage 2: LLM Director (Qwen2.5-7B)
Stage 3: Rendering (handled separately via API)
"""
from __future__ import annotations
import logging
import os
import asyncio
from typing import AsyncGenerator, Optional, Callable
from backend.services.vram_manager import vram_manager
from backend.services.whisper_gpu import whisper_gpu
from backend.services.face_detector import face_detector
from backend.services.audio_analyzer import audio_analyzer
from backend.services.context_builder import context_builder
from backend.services.llm_director import llm_director
from backend.schemas.moment_instruction import Stage1Context, DirectorOutput

logger = logging.getLogger(__name__)


def _signal_for_window(ctx, start, end):
    """Return (avg_rms, peak_energy, speech_chars) for a time window from Stage 1 data.
    Defensive against both object- and dict-shaped entries."""
    if ctx is None:
        return (0.0, 0.0, 0.0)
    aa = getattr(ctx, "audio_analysis", None)
    avg_rms = peak_energy = 0.0
    if aa is not None:
        rms_list = getattr(aa, "rms_timeline", None) or []
        vals = []
        for r in rms_list:
            t = r.get("time") if isinstance(r, dict) else getattr(r, "time", None)
            v = r.get("rms") if isinstance(r, dict) else getattr(r, "rms", None)
            if t is not None and v is not None and start <= float(t) <= end:
                vals.append(float(v))
        avg_rms = sum(vals) / len(vals) if vals else 0.0
        for p in (getattr(aa, "peaks", None) or []):
            t = p.get("timestamp") if isinstance(p, dict) else getattr(p, "timestamp", None)
            mag = p.get("magnitude") if isinstance(p, dict) else getattr(p, "magnitude", 0.0)
            if t is not None and start <= float(t) <= end:
                peak_energy += float(mag or 0.0)
    chars = 0
    for seg in (getattr(ctx, "transcript", None) or []):
        s = seg.get("start") if isinstance(seg, dict) else getattr(seg, "start", None)
        e = seg.get("end") if isinstance(seg, dict) else getattr(seg, "end", None)
        txt = seg.get("text") if isinstance(seg, dict) else getattr(seg, "text", "")
        if s is not None and e is not None and float(e) >= start and float(s) <= end:
            chars += len(txt or "")
    return (avg_rms, peak_energy, float(chars))


def _enforce_constraints(moments, min_duration, max_duration, max_moments, video_duration, ctx=None):
    """Deterministically enforce the user's Detection Settings on LLM output.

    The local LLM frequently ignores the prompt rules: it returns clips that are
    far too short (4-24s), pads the list, and omits virality_score (so every clip
    collapses to the schema default of 50). We fix all of that here:
      * size each clip to a target length that scales with its signal strength,
        so durations vary naturally between min_duration and max_duration;
      * trim clips longer than max_duration, drop ones too short to be usable;
      * compute a REAL virality_score from audio energy + speech density when the
        model failed to differentiate (all scores identical);
      * remove heavy overlaps, sort by score, cap to max_moments, then restore
        chronological order for display.
    """
    # 1) Sample signals per moment (widen short windows so density is comparable).
    raw = []
    for mo in moments:
        start = max(0.0, float(mo.start))
        end = float(mo.end)
        if end <= start:
            raw.append(None)
            continue
        we = max(end, min(start + min_duration, video_duration))
        raw.append(_signal_for_window(ctx, start, we))

    def _normalizer(idx):
        vals = [r[idx] for r in raw if r]
        lo, hi = (min(vals), max(vals)) if vals else (0.0, 0.0)
        rng = hi - lo
        return lambda v: ((v - lo) / rng) if rng > 1e-9 else 0.5
    n_rms, n_peak, n_chars = _normalizer(0), _normalizer(1), _normalizer(2)

    model_scores = [float(getattr(m, "virality_score", 0) or 0) for m in moments]
    model_has_variance = (max(model_scores) - min(model_scores) > 1.0) if model_scores else False

    floor = min(min_duration, video_duration)
    cleaned = []
    for mo, r in zip(moments, raw):
        if r is None:
            continue
        start = max(0.0, float(mo.start))
        end = float(mo.end)
        # Composite signal strength 0..1 (peaks weigh most, then loudness, then speech).
        comp = 0.45 * n_peak(r[1]) + 0.35 * n_rms(r[0]) + 0.20 * n_chars(r[2])
        # Target length scales with signal: strong moments get longer clips.
        target = min_duration + (max_duration - min_duration) * comp
        if end - start < target:
            end = min(start + target, video_duration)
            if end - start < min_duration:
                start = max(0.0, end - min_duration)
        if end - start > max_duration:
            end = start + max_duration
        if end - start < min(floor, 15.0) - 0.01:
            continue
        mo.start = round(start, 2)
        mo.end = round(end, 2)
        # Score: trust the model only if it actually differentiated; otherwise
        # derive a varied, meaningful score from the signals (45..95).
        if model_has_variance:
            if not getattr(mo, "virality_score", None):
                mo.virality_score = 50
        else:
            mo.virality_score = round(45 + 50 * comp)
        cleaned.append(mo)

    cleaned.sort(key=lambda x: x.virality_score or 0, reverse=True)
    kept = []
    for mo in cleaned:
        overlapped = False
        for k in kept:
            inter = min(mo.end, k.end) - max(mo.start, k.start)
            if inter > 0 and inter > 0.5 * min(mo.end - mo.start, k.end - k.start):
                overlapped = True
                break
        if not overlapped:
            kept.append(mo)

    kept = kept[:max_moments]
    kept.sort(key=lambda x: x.start)  # chronological for display
    return kept

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
        
        # Time estimates for RTX 5060 (8GB). Stage 1 is dominated by YOLO face
        # tracking (roughly real-time-ish per sampled frame); Stage 2 by the LLM.
        # These are rough upper bounds — actual time varies with scene complexity.
        if video_duration_min <= 30:
            est_stage1 = "5-10мин"
            est_stage2 = "2-4мин"
            est_total = "7-14 минут"
        elif video_duration_min <= 60:
            est_stage1 = "10-20мин"
            est_stage2 = "4-7мин"
            est_total = "15-27 минут"
        else:
            est_stage1 = "20-35мин"
            est_stage2 = "7-12мин"
            est_total = "27-47 минут"
        
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

        transcript = await asyncio.to_thread(whisper_gpu.transcribe, video_path)
        vram_manager.unload_all()  # Safety flush
        
        # Count words and segments for granular progress detail
        total_words = sum(len(seg.text.split()) for seg in transcript) if transcript else 0
        total_segments = len(transcript) if transcript else 0

        if progress_callback:
            await progress_callback({
                "stage": 1,
                "step": "transcription_done",
                "progress": 0.28,
                "detail": f"{total_words} слов, {total_segments} сегментов"
            })

        if progress_callback:
            await progress_callback({"stage": 1, "step": "face_detection", "progress": 0.30})

        face_timeline = await asyncio.to_thread(face_detector.detect_faces_timeline, video_path)
        vram_manager.unload_all()  # Safety flush
        
        face_count = len(face_timeline.unique_face_ids) if face_timeline else 0

        if progress_callback:
            await progress_callback({
                "stage": 1,
                "step": "yolo_done",
                "progress": 0.48,
                "detail": f"{face_count} лиц"
            })

        if progress_callback:
            await progress_callback({"stage": 1, "step": "audio_analysis", "progress": 0.50})

        audio_analysis = await asyncio.to_thread(audio_analyzer.analyze, video_path)
        
        # Extract peak count from audio analysis
        peak_count = len(audio_analysis.peaks) if hasattr(audio_analysis, 'peaks') and audio_analysis.peaks else 0
        
        if progress_callback:
            await progress_callback({
                "stage": 1,
                "step": "audio_done",
                "progress": 0.57,
                "detail": f"{peak_count} пиков"
            })
        
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
        context_chunks = await asyncio.to_thread(context_builder.build_chunks, ctx, user_instructions)
        
        # Estimate total LLM time based on number of chunks
        chunk_analyze_time = 90  # ~60-120s per chunk on RTX 5060 (Qwen3-8B Q4, reasoning)
        est_llm_time = len(context_chunks) * chunk_analyze_time
        if len(context_chunks) > 1:
            est_llm_time += 20  # +20s for consolidation pass
        
        logger.info(f"🧠 [LLM] Ожидаемое время анализа: ~{est_llm_time}с ({len(context_chunks)} чанков)")

        if progress_callback:
            await progress_callback({"stage": 2, "step": "llm_analysis", "progress": 0.70})

        # Create asyncio-compatible LLM progress callback wrapper
        _loop = asyncio.get_event_loop()
        def _llm_progress(chunk_i: int, total: int, phase: str = "chunk"):
            prog = 0.70 + (chunk_i / max(total, 1)) * 0.14
            step_name = "llm_chunk" if phase == "chunk" else "llm_consolidate"
            coro = progress_callback({
                "stage": 2,
                "step": step_name,
                "progress": prog,
                "detail": f"Чанк {chunk_i}/{total}"
            })
            asyncio.run_coroutine_threadsafe(coro, _loop)

        director_output = await asyncio.to_thread(
            llm_director.analyze, context_chunks, user_instructions, _llm_progress,
            min_duration, max_duration, max_moments
        )
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
        # Enforce Detection Settings deterministically (LLM often ignores them).
        director_output.moments = _enforce_constraints(
            director_output.moments, min_duration, max_duration, max_moments, video_duration, ctx,
        )

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