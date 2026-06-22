"""GPU-first Whisper transcription using faster-whisper distil-large-v3.

This is the MAIN transcription service for GPU pipeline. Legacy speech_scorer.py
is only used by CPU fallback pipeline.
"""
from __future__ import annotations
import logging
import os
import random
import subprocess
import tempfile
from collections import defaultdict
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

    def _detect_language_smart(self, model, audio_path: str, duration_minutes: float) -> Optional[str]:
        """Smart language detection using multiple samples across the video.
        
        Args:
            model: Loaded WhisperModel instance
            audio_path: Path to audio/video file
            duration_minutes: Video duration in minutes
            
        Returns:
            Detected language code or None if detection fails
        """
        # Calculate number of samples based on video duration
        if duration_minutes < 5:
            num_samples = max(3, int(duration_minutes))  # At least 3, proportional to duration
        else:
            num_samples = 10
        
        duration_seconds = duration_minutes * 60
        
        # Skip first and last 60 seconds to avoid intros/outros
        skip_start = 60
        skip_end = 60
        
        # If video is too short, reduce skip margins
        if duration_seconds < 180:  # Less than 3 minutes
            skip_start = min(30, duration_seconds * 0.1)
            skip_end = min(30, duration_seconds * 0.1)
        
        usable_duration = duration_seconds - skip_start - skip_end
        if usable_duration < 30:
            logger.warning(f"🎙️  [Whisper] Видео слишком короткое ({duration_seconds:.0f}с) для умной детекции языка, используем стандартный метод")
            return None
        
        # Generate random sample positions
        sample_positions = []
        for i in range(num_samples):
            # Evenly distribute samples across usable duration with some randomness
            base_pos = skip_start + (usable_duration / num_samples) * i
            random_offset = random.uniform(-30, 30)  # Add some randomness
            sample_pos = max(skip_start, min(duration_seconds - skip_end - 30, base_pos + random_offset))
            sample_positions.append(sample_pos)
        
        # Sort positions for logging clarity
        sample_positions.sort()
        
        logger.info(f"🎙️  [Whisper] Умная детекция языка: {num_samples} проб по 30 секунд")
        
        # Collect language votes with probabilities
        language_votes = defaultdict(float)
        successful_samples = 0
        
        for idx, start_time in enumerate(sample_positions, 1):
            try:
                # Extract 30-second chunk using ffmpeg
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                    temp_path = temp_audio.name
                
                # Format timestamp for ffmpeg (HH:MM:SS)
                hours = int(start_time // 3600)
                minutes = int((start_time % 3600) // 60)
                seconds = int(start_time % 60)
                timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                # Extract chunk with ffmpeg
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss", timestamp,
                    "-i", audio_path,
                    "-t", "30",  # 30 seconds duration
                    "-ar", "16000",  # 16kHz sample rate (whisper expects this)
                    "-ac", "1",  # Mono
                    "-f", "wav",
                    "-loglevel", "error",
                    temp_path
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                # Detect language on this chunk
                lang_info = model.detect_language(temp_path)
                detected_lang = lang_info[0][0]  # detect_language returns [(lang_code, probability), ...]
                probability = lang_info[0][1]
                
                # Add weighted vote
                language_votes[detected_lang] += probability
                successful_samples += 1
                
                # Format time for logging
                time_mins = int(start_time // 60)
                time_secs = int(start_time % 60)
                
                # Language name mapping
                lang_map = {
                    'ru': 'русский',
                    'en': 'английский',
                    'es': 'испанский',
                    'fr': 'французский',
                    'de': 'немецкий',
                }
                lang_name = lang_map.get(detected_lang, detected_lang)
                
                logger.info(f"🎙️  [Whisper] Проба {idx}/{num_samples} на {time_mins:02d}:{time_secs:02d} → {lang_name} ({int(probability * 100)}%)")
                
            except Exception as e:
                logger.warning(f"🎙️  [Whisper] Ошибка при обработке пробы {idx}/{num_samples}: {e}")
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
        
        # Check if we have enough successful samples
        if successful_samples < 3:
            logger.warning(f"🎙️  [Whisper] Недостаточно успешных проб ({successful_samples}/3), используем стандартный метод")
            return None
        
        # Determine winner by total probability
        if not language_votes:
            return None
        
        winner_lang = max(language_votes.items(), key=lambda x: x[1])
        detected_language = winner_lang[0]
        avg_confidence = winner_lang[1] / successful_samples
        
        # Language name for logging
        lang_map = {
            'ru': 'русский',
            'en': 'английский',
            'es': 'испанский',
            'fr': 'французский',
            'de': 'немецкий',
        }
        lang_name = lang_map.get(detected_language, detected_language)
        
        logger.info(f"🎙️  [Whisper] Язык определён по {successful_samples} пробам: {lang_name} (средняя уверенность: {int(avg_confidence * 100)}%)")
        
        return detected_language

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
        
        # Smart language detection if not specified
        if language is None:
            detected_lang = self._detect_language_smart(model, audio_path, video_duration_min)
            if detected_lang:
                language = detected_lang
                logger.info(f"🎙️  [Whisper] Используем определённый язык для транскрипции: {language}")
        
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
