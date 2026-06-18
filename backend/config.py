"""Configuration for ClipForge application."""
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
DOWNLOADS_DIR = WORKSPACE_DIR / "downloads"
OUTPUT_DIR = WORKSPACE_DIR / "output"
TEMP_DIR = WORKSPACE_DIR / "temp"
MODELS_DIR = WORKSPACE_DIR / "models"
BANNERS_DIR = WORKSPACE_DIR / "banners"
WHISPER_MODEL_DIR = MODELS_DIR / "whisper-base"
DB_PATH = WORKSPACE_DIR / "clipforge.db"

# Create workspace directories on import
for directory in [DOWNLOADS_DIR, OUTPUT_DIR, TEMP_DIR, MODELS_DIR, BANNERS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Whisper model configuration
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")  # base = ~150MB, free
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", None)  # Force language (e.g., 'ru', 'en'), None = auto-detect
WHISPER_CONFIDENCE_THRESHOLD = 0.65  # Re-sample if detected language confidence < this value

# YouTube API configuration
YOUTUBE_CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
YOUTUBE_CREDENTIALS_FILE = WORKSPACE_DIR / "youtube_credentials.json"

# Processing defaults
DEFAULT_MIN_DURATION = 30  # seconds
DEFAULT_MAX_DURATION = 90  # seconds
DEFAULT_MAX_MOMENTS = 15

# Scoring weights for moment detection
SCORE_WEIGHTS = {
    "speech_content": 0.5,
    "audio_energy": 0.3,
    "scene_changes": 0.2,
}

# Emotion keywords for speech scoring (multilingual)
EMOTION_KEYWORDS = [
    # English
    "amazing", "incredible", "wow", "unbelievable", "secret", "mistake", 
    "hack", "tip", "problem", "solution", "shocking", "never", "always", 
    "worst", "best", "finally", "discovered", "revealed",
    # Russian
    "невероятно", "потрясающе", "никогда", "всегда", "наконец", 
    "открыл", "секрет", "лайфхак", "проблема", "решение", "ошибка",
]
