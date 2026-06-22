"""GPU-first Whisper transcription using faster-whisper distil-large-v3.

This is the MAIN transcription service for GPU pipeline. Legacy speech_scorer.py
is only used by CPU fallback pipeline.
"""
from __future__ import annotations
import logging
from typing import List, Optional
from backend.gpu_config import WHISPER_GPU_MODEL, WHISPER_GPU_COMPUTE, MODELS_DIR
from backend.services.vram_manager import vram_manager
from backend.schemas.moment_instruction import TranscriptSegment, TranscriptWord

logger = logging.getLogger(__name__)


class WhisperGPU:
    """GPU-first Whisper transcription.
    
    Uses CUDA fp16 when GPU is available, CPU int8 as emergency fallback.
    Automatically unloads model after transcription completes.
    """

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> List[TranscriptSegment]:
        """Transcribe audio file with word-level timestamps.
        
        Args:
            audio_path: Path to audio/video file
            language: Optional language code (None = auto-detect)
            
        Returns:
            List of transcript segments with word timestamps
        """
        from faster_whisper import WhisperModel
        import time
        import cv2

        device = vram_manager.device
        compute_type = WHISPER_GPU_COMPUTE if device == "cuda" else "int8"
        
        # Get video duration for logging
        cap = cv2.VideoCapture(audio_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration_min = (total_frames / fps) / 60.0
        cap.release()

        load_start = time.time()
        logger.info(f"🎙️  [Whisper] Загрузка модели distil-large-v3 (~2.4 GB VRAM)...")

        def _load():
            return WhisperModel(
                WHISPER_GPU_MODEL,
                device=device,
                compute_type=compute_type,
                download_root=str(MODELS_DIR / "whisper"),
            )

        model = vram_manager.load_model("whisper", _load)
        load_time = time.time() - load_start
        logger.info(f"🎙️  [Whisper] Модель загружена за {load_time:.1f}с")
        logger.info(f"🎙️  [Whisper] Транскрибирую аудио ({video_duration_min:.1f} мин)...")
        
        transcribe_start = time.time()
        segments_raw, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
        )

        segments: List[TranscriptSegment] = []
        total_words = 0
        for seg in segments_raw:
            words = []
            if seg.words:
                words = [
                    TranscriptWord(
                        word=w.word,
                        start=w.start,
                        end=w.end,
                        probability=w.probability
                    )
                    for w in seg.words
                ]
                total_words += len(words)
            segments.append(TranscriptSegment(
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                language=info.language,
                words=words,
            ))
        
        transcribe_time = time.time() - transcribe_start
        
        # Language mapping for display
        lang_map = {
            'ru': 'русский',
            'en': 'английский',
            'es': 'испанский',
            'fr': 'французский',
            'de': 'немецкий',
        }
        lang_name = lang_map.get(info.language, info.language)
        prob_percent = int(info.language_probability * 100) if hasattr(info, 'language_probability') else 0
        
        logger.info(f"🎙️  [Whisper] Обнаруженный язык: {lang_name} ({prob_percent}%)")
        logger.info(f"🎙️  [Whisper] Транскрипция завершена: {total_words} слов, {len(segments)} сегментов за {transcribe_time:.1f}с")

        vram_manager.unload_model("whisper")
        logger.info(f"🎙️  [Whisper] Модель выгружена из VRAM")
        return segments


# Global singleton instance
whisper_gpu = WhisperGPU()
