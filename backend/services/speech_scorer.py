"""Speech transcription and content scoring using faster-whisper."""
import logging
import re
from typing import Dict, List, Optional
from collections import Counter
from backend.config import WHISPER_MODEL_SIZE, EMOTION_KEYWORDS

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
            _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
            logger.info(f"Loaded Whisper model: {WHISPER_MODEL_SIZE}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return None
    
    return _whisper_model


def transcribe_video(video_path: str) -> Optional[List[Dict]]:
    """
    Transcribe video audio using faster-whisper.
    
    Returns:
        List of segments with text, start, and end times, or None if unavailable
    """
    model = get_whisper_model()
    if model is None:
        return None
    
    try:
        segments, info = model.transcribe(video_path, beam_size=5)
        
        result = []
        for segment in segments:
            result.append({
                'text': segment.text,
                'start': segment.start,
                'end': segment.end,
                'words': getattr(segment, 'words', []),
            })
        
        logger.info(f"Transcribed {len(result)} segments. Language: {info.language}")
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


async def analyze_speech_content(video_path: str) -> Optional[Dict[float, float]]:
    """
    Analyze speech content and generate scores for moment detection.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dict mapping timestamps to speech content scores (0-100), or None if unavailable
    """
    segments = transcribe_video(video_path)
    
    if segments is None or len(segments) == 0:
        print("No transcription available, skipping speech scoring")
        return None
    
    scores = generate_speech_scores(segments)
    
    print(f"Generated speech scores for {len(scores)} segments")
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
