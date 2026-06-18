"""Speech transcription and content scoring using faster-whisper."""
import logging
import re
import tempfile
import subprocess
from typing import Dict, List, Optional, Tuple
from collections import Counter
from pathlib import Path
from backend.config import (
    WHISPER_MODEL_SIZE, 
    WHISPER_MODEL_DIR, 
    EMOTION_KEYWORDS,
    WHISPER_LANGUAGE,
    WHISPER_CONFIDENCE_THRESHOLD
)

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available. Speech scoring will be disabled.")


_whisper_model: Optional['WhisperModel'] = None


def get_whisper_model():
    """Lazy load Whisper model (singleton)."""
    global _whisper_model
    if not WHISPER_AVAILABLE:
        return None
    
    if _whisper_model is None:
        try:
            # Use local model path if it exists, otherwise fall back to model name
            if WHISPER_MODEL_DIR.exists():
                model_path = str(WHISPER_MODEL_DIR)
                logger.info(f"Loading Whisper model from local path: {model_path}")
            else:
                model_path = WHISPER_MODEL_SIZE
                logger.warning(f"Local Whisper model not found. Downloading '{WHISPER_MODEL_SIZE}' from HuggingFace...")
            
            _whisper_model = WhisperModel(model_path, device="cpu", compute_type="int8")
            logger.info(f"Loaded Whisper model successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return None
    
    return _whisper_model


def extract_audio_segment(video_path: str, start_sec: float, duration_sec: float, output_path: str) -> bool:
    """
    Extract a specific audio segment from a video using FFmpeg.
    
    Args:
        video_path: Path to source video
        start_sec: Start time in seconds
        duration_sec: Duration to extract in seconds
        output_path: Where to save the extracted audio
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-ss', str(start_sec),
            '-i', video_path,
            '-t', str(duration_sec),
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # WAV format for Whisper
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',  # Mono
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction failed: {e.stderr}")
        return False


def detect_language_from_sample(model, video_path: str, start_sec: float = 0, duration_sec: float = 60) -> Tuple[str, float]:
    """
    Detect language from a specific segment of the video.
    
    Args:
        model: Whisper model instance
        video_path: Path to video file
        start_sec: Start time in seconds
        duration_sec: Duration to sample in seconds
        
    Returns:
        Tuple of (language_code, confidence)
    """
    # Extract audio sample to temp file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        if not extract_audio_segment(video_path, start_sec, duration_sec, tmp_path):
            logger.warning(f"Failed to extract audio sample from {start_sec}s")
            return ('ru', 0.0)  # Default fallback
        
        # Detect language from the sample
        segments, info = model.transcribe(tmp_path, beam_size=5)
        
        # Consume first segment to trigger language detection
        _ = next(segments, None)
        
        return (info.language, info.language_probability)
    
    except Exception as e:
        logger.error(f"Language detection failed: {e}")
        return ('ru', 0.0)
    
    finally:
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except:
            pass


def smart_language_detection(model, video_path: str) -> Tuple[str, float]:
    """
    Smart multi-sample language detection with fallback logic.
    
    Samples multiple segments of the video to improve confidence.
    Defaults to 'ru' if confidence is consistently low.
    
    Returns:
        Tuple of (language_code, confidence)
    """
    # If WHISPER_LANGUAGE is set, use that and skip detection
    if WHISPER_LANGUAGE:
        logger.info(f"Using forced language from config: {WHISPER_LANGUAGE}")
        return (WHISPER_LANGUAGE, 1.0)
    
    # Try first 60 seconds
    logger.info("Detecting language from first 60 seconds...")
    lang1, conf1 = detect_language_from_sample(model, video_path, start_sec=0, duration_sec=60)
    logger.info(f"First sample: language={lang1}, confidence={conf1:.2f}")
    
    # If high confidence, we're done
    if conf1 >= WHISPER_CONFIDENCE_THRESHOLD:
        return (lang1, conf1)
    
    # Low confidence — try middle segment (5 minutes in)
    logger.warning(f"Low confidence ({conf1:.2f} < {WHISPER_CONFIDENCE_THRESHOLD}). Sampling middle segment...")
    lang2, conf2 = detect_language_from_sample(model, video_path, start_sec=300, duration_sec=60)
    logger.info(f"Middle sample: language={lang2}, confidence={conf2:.2f}")
    
    # Use the higher-confidence result
    if conf2 > conf1:
        best_lang, best_conf = lang2, conf2
    else:
        best_lang, best_conf = lang1, conf1
    
    # If still low confidence, default to Russian (user is Russian)
    if best_conf < WHISPER_CONFIDENCE_THRESHOLD:
        logger.warning(
            f"Language detection uncertain (best confidence: {best_conf:.2f}). "
            f"Detected as '{best_lang}' but defaulting to 'ru' for reliability. "
            f"Set WHISPER_LANGUAGE env var to force a specific language."
        )
        return ('ru', best_conf)
    
    return (best_lang, best_conf)


def transcribe_video(video_path: str) -> Optional[List[Dict]]:
    """
    Transcribe video audio using faster-whisper with smart language detection.
    
    Returns:
        List of segments with text, start, and end times, or None if unavailable
    """
    model = get_whisper_model()
    if model is None:
        return None
    
    try:
        # Smart language detection
        detected_lang, confidence = smart_language_detection(model, video_path)
        logger.info(f"Using language: {detected_lang} (confidence: {confidence:.2f})")
        
        # Transcribe with detected/forced language
        segments, info = model.transcribe(
            video_path, 
            beam_size=5,
            language=detected_lang  # Force the detected/configured language
        )
        
        result = []
        for segment in segments:
            result.append({
                'text': segment.text,
                'start': segment.start,
                'end': segment.end,
                'words': getattr(segment, 'words', []),
            })
        
        logger.info(f"Transcribed {len(result)} segments. Language: {detected_lang} (confidence: {confidence:.2f})")
        return result
    
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None


def count_questions(text: str) -> int:
    """Count question marks in text."""
    return text.count('?')


def count_exclamations(text: str) -> int:
    """Count exclamation marks in text."""
    return text.count('!')


def count_emotion_keywords(text: str) -> int:
    """Count emotion keywords (case-insensitive)."""
    text_lower = text.lower()
    count = 0
    for keyword in EMOTION_KEYWORDS:
        count += text_lower.count(keyword.lower())
    return count


def calculate_speech_rate(segment: Dict) -> float:
    """Calculate words per second in a segment."""
    text = segment['text']
    duration = segment['end'] - segment['start']
    
    if duration <= 0:
        return 0.0
    
    word_count = len(text.split())
    return word_count / duration


def score_segment(segment: Dict, context: Optional[List[Dict]] = None) -> float:
    """
    Score a single transcript segment based on content heuristics.
    
    Args:
        segment: Transcript segment with text, start, end
        context: Optional list of previous segments for context analysis
        
    Returns:
        Score from 0-100
    """
    text = segment['text']
    score = 0.0
    
    # Question density (questions are engaging)
    questions = count_questions(text)
    score += questions * 30
    
    # Exclamation density (excitement markers)
    exclamations = count_exclamations(text)
    score += exclamations * 20
    
    # Emotion keyword matching
    emotion_keywords = count_emotion_keywords(text)
    score += emotion_keywords * 10
    
    # Speech pace (fast speech can indicate excitement)
    speech_rate = calculate_speech_rate(segment)
    if speech_rate > 3.0:  # More than 3 words per second
        score += 15
    
    # Topic shift detection (comparing word frequency with context)
    if context and len(context) > 0:
        # Simple topic change: check if vocabulary is significantly different
        current_words = set(text.lower().split())
        context_text = " ".join([s['text'] for s in context[-3:]])  # Last 3 segments
        context_words = set(context_text.lower().split())
        
        if current_words and context_words:
            overlap = len(current_words & context_words) / len(current_words)
            if overlap < 0.3:  # Less than 30% overlap = topic change
                score += 20
    
    # Cap at 100
    return min(100, score)


def generate_speech_scores(segments: List[Dict]) -> Dict[float, float]:
    """
    Generate speech content scores for all segments.
    
    Args:
        segments: List of transcript segments
        
    Returns:
        Dict mapping timestamp (midpoint of segment) to score
    """
    scores = {}
    
    for i, segment in enumerate(segments):
        # Get context (previous segments)
        context = segments[max(0, i-5):i] if i > 0 else []
        
        # Score this segment
        score = score_segment(segment, context)
        
        # Use midpoint timestamp as key
        midpoint = (segment['start'] + segment['end']) / 2
        scores[midpoint] = score
    
    return scores


def analyze_speech_content(video_path: str) -> Optional[Dict[float, float]]:
    """
    Analyze speech content and generate scores for moment detection.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dict mapping timestamps to speech content scores (0-100), or None if unavailable
    """
    segments = transcribe_video(video_path)
    
    if segments is None or len(segments) == 0:
        logger.info("No transcription available, skipping speech scoring")
        return None
    
    scores = generate_speech_scores(segments)
    
    logger.info(f"Generated speech scores for {len(scores)} segments")
    return scores


def generate_subtitles_file(video_path: str, output_path: str) -> bool:
    """
    Generate SRT subtitle file from video transcription.
    
    Args:
        video_path: Path to video file
        output_path: Path to save .srt file
        
    Returns:
        True if successful, False otherwise
    """
    segments = transcribe_video(video_path)
    
    if segments is None or len(segments) == 0:
        return False
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, start=1):
                # Convert timestamps to SRT format (HH:MM:SS,mmm)
                start_time = format_srt_time(segment['start'])
                end_time = format_srt_time(segment['end'])
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment['text'].strip()}\n")
                f.write("\n")
        
        return True
    
    except Exception as e:
        print(f"Failed to generate subtitles: {e}")
        return False


def format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
