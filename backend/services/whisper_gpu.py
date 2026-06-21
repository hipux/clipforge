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

        device = vram_manager.device
        compute_type = WHISPER_GPU_COMPUTE if device == "cuda" else "int8"

        logger.info(f"Loading Whisper distil-large-v3 on {device} ({compute_type})")

        def _load():
            return WhisperModel(
                WHISPER_GPU_MODEL,
                device=device,
                compute_type=compute_type,
                download_root=str(MODELS_DIR / "whisper"),
            )

        model = vram_manager.load_model("whisper", _load)

        logger.info("Transcribing audio...")
        segments_raw, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
        )

        segments: List[TranscriptSegment] = []
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
            segments.append(TranscriptSegment(
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                language=info.language,
                words=words,
            ))

        vram_manager.unload_model("whisper")
        logger.info(f"Transcription complete: {len(segments)} segments, language={info.language}")
        return segments


# Global singleton instance
whisper_gpu = WhisperGPU()
