"""GPU pipeline configuration and model paths.

This module centralizes all GPU pipeline configuration via environment variables
with the CLIPFORGE_ prefix. Models are downloaded automatically on first run.
"""
import os
from pathlib import Path

# Project root = 2 levels up from backend/gpu_config.py
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = Path(os.getenv("CLIPFORGE_MODELS_DIR", str(PROJECT_ROOT / "models")))
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Redirect HuggingFace cache to models/whisper/
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "whisper"))

# ─── Whisper Configuration ─────────────────────────────────────────────────
# IMPORTANT: distil-large-v3 is English-only despite claiming multilingual support.
# For Russian/multilingual content we use the full large-v3 (~2.9 GB VRAM fp16).
# RTX 5060 has 8 GB VRAM — large-v3 fits comfortably.
WHISPER_GPU_MODEL = os.getenv("CLIPFORGE_WHISPER_MODEL", "Systran/faster-whisper-large-v3")
WHISPER_GPU_COMPUTE = os.getenv("CLIPFORGE_WHISPER_COMPUTE", "float16")

# ─── Face Detection Configuration ──────────────────────────────────────────
FACE_MODEL_PATH = MODELS_DIR / "yolov8n-face.pt"
FACE_SAMPLE_FPS = float(os.getenv("CLIPFORGE_FACE_SAMPLE_FPS", "1.0"))
# Confidence threshold for YOLO detection. 0.55 catches real faces on busy
# frames without flooding the timeline with poster/logo false positives.
FACE_CONFIDENCE_THRESHOLD = float(os.getenv("CLIPFORGE_FACE_CONF", "0.55"))
# Min relative bbox area kept (0..1, normalised by frame). Bboxes smaller
# than this are dropped as likely artifacts (posters, watermarks).
# 0.01 = 1% of the frame; below this YOLO is usually wrong.
MIN_BBOX_AREA = float(os.getenv("CLIPFORGE_FACE_MIN_AREA", "0.012"))
# Tracks must contain at least N individual detections across the video to
# survive post-process. Each frame's track keeps adding detections, so a
# real face orbiting across the frame produces 10+. A poster flickering in
# SOS noise produces 1-3; drop them.
MIN_DETECTIONS_PER_TRACK = int(os.getenv("CLIPFORGE_FACE_MIN_DETECTIONS", "3"))

# ─── YamNet Audio-Event Classifier (ONNX) ─────────────────────────────────
# Semantic audio events (laughter, applause, cheering...) — stronger virality
# signal than raw RMS energy. ONNX port so no TensorFlow dependency. Optional:
# if these files are absent, the classifier degrades to a no-op (events=[]).
YAMNET_ONNX_PATH = os.getenv("CLIPFORGE_YAMNET_ONNX", str(MODELS_DIR / "yamnet" / "yamnet.onnx"))
YAMNET_CLASSMAP_PATH = os.getenv("CLIPFORGE_YAMNET_CLASSMAP", str(MODELS_DIR / "yamnet" / "yamnet_class_map.csv"))

# ─── LLM Configuration (Qwen3-8B GGUF) ─────────────────────────────────────
QWEN_MODEL_REPO = "Qwen/Qwen3-8B-GGUF"
QWEN_MODEL_FILE = "Qwen3-8B-Q4_K_M.gguf"  # Note: case-sensitive filename on HuggingFace!
QWEN_MODEL_PATH = MODELS_DIR / QWEN_MODEL_FILE
QWEN_N_CTX = int(os.getenv("CLIPFORGE_QWEN_N_CTX", "8192"))  # was 32768: a 32k KV-cache (~3-4GB) plus the ~5GB Q4 model exceeds 8GB VRAM and spills to system RAM, making generation very slow. Each chunk is only ~4-5k tokens, so 16k is ample and keeps everything on-GPU.
QWEN_N_GPU_LAYERS = int(os.getenv("CLIPFORGE_QWEN_N_GPU_LAYERS", "-1"))  # -1 = all layers on GPU
QWEN_TEMPERATURE = float(os.getenv("CLIPFORGE_QWEN_TEMP", "0.3"))
QWEN_PRESENCE_PENALTY = float(os.getenv("CLIPFORGE_QWEN_PRESENCE", "1.5"))
QWEN_TOP_P = float(os.getenv("CLIPFORGE_QWEN_TOP_P", "0.95"))

# ─── NVENC Encoder Configuration ───────────────────────────────────────────
NVENC_PRESET = os.getenv("CLIPFORGE_NVENC_PRESET", "p7")
NVENC_CQ = int(os.getenv("CLIPFORGE_NVENC_CQ", "18"))  # 20->18: less blocking/banding on the blurred background (flat dark gradients compressed too hard)
NVENC_RC_LOOKAHEAD = int(os.getenv("CLIPFORGE_NVENC_LOOKAHEAD", "20"))

# ─── Pipeline Mode ─────────────────────────────────────────────────────────
# GPU-first: "true" (default) = use GPU if CUDA available
#            "false" = force CPU legacy pipeline
#            "auto" = same as "true"
USE_GPU_PIPELINE = os.getenv("CLIPFORGE_USE_GPU", "true")
VRAM_SAFETY_MARGIN_GB = float(os.getenv("CLIPFORGE_VRAM_MARGIN", "0.5"))


# ─── Gemini LLM (cloud, optional) ──────────────────────────────────────────
# Gemini 2.5 Flash is the PRIMARY director when configured: far better prompt
# adherence + reasoning than local Qwen3-8B, and it is MULTIMODAL (frames can
# be sent later to distinguish host reaction from embedded footage).
#
# IMPORTANT for RU: Gemini API is region-blocked from Russia (the API checks
# the caller's IP geolocation). Set CLIPFORGE_GEMINI_PROXY to an HTTP(S) proxy
# (datacenter VPS in a supported region works fine) so all API calls egress
# from a supported region. If no key/proxy is set, the pipeline silently falls
# back to local Qwen3-8B.
GEMINI_ENABLED = os.getenv("CLIPFORGE_GEMINI_ENABLED", "true").lower() == "true"
GEMINI_API_KEY = os.getenv("CLIPFORGE_GEMINI_API_KEY", "")  # set in .env (gitignored)
# Default to Gemini 3.5 Flash (GA May 2026, free-tier available, 1M input
# tokens / 65K output tokens — same model the official cookbook defaults to).
# Older `gemini-2.5-flash` keeps working for users who explicitly pin it. The
# older preview alias `gemini-3-flash-preview` is also valid but pinned to the
# Dec-2025 cutoff, prefer the GA name. Avoid `gemini-3.1-pro-preview` on the
# free tier — Google requires paid Tier 1 for Pro.
GEMINI_MODEL = os.getenv("CLIPFORGE_GEMINI_MODEL", "gemini-3.5-flash")
# Proxy for region-blocked access. Accepts http://, https://, or socks5:// URLs.
# Datacenter IPs work (the API keys on IP, not residential status).
GEMINI_PROXY = os.getenv("CLIPFORGE_GEMINI_PROXY", "")
# Per-request timeout. Gemini 3.5 Flash answers in seconds; 120s is a safe
# ceiling (1M input tokens + 65K output reasoning can take longer on big
# requests — bump this up if you see transient timeouts).
GEMINI_TIMEOUT = float(os.getenv("CLIPFORGE_GEMINI_TIMEOUT", "120"))
# Hard cap on attempts before falling back to Qwen. We retry on TRANSIENT
# errors (503/429/timeout) only — auth/region errors are NOT retried (re-trying
# a 403 region-block just wastes seconds before falling back).
GEMINI_MAX_RETRIES = int(os.getenv("CLIPFORGE_GEMINI_MAX_RETRIES", "3"))
# Base delay between retries in seconds — exponentially backed off (×2 per attempt).
# Total worst-case wait on a transient 503 with MAX_RETRIES=3: 5+10+20 = 35s.
GEMINI_RETRY_BASE_DELAY = float(os.getenv("CLIPFORGE_GEMINI_RETRY_DELAY", "5"))

# Memoize a successful `check_health()` so we don't burn an RPD credit on
# EVERY detection. On the Gemini free tier (≈20 RPD), a separate pre-flight
# call per video halves the daily budget. Default 5 minutes — long enough to
# cover a typical session of 5-10 videos, short enough that a rate-limit
# recovery is detected within reasonable time.
# Set to 0 to disable caching (run pre-flight every time).
GEMINI_HEALTH_TTL = float(os.getenv("CLIPFORGE_GEMINI_HEALTH_TTL", "300"))

# Gemini API status codes we treat as TRANSIENT and retry. Anything else
# (400 bad request, 403 region-block / bad key, 404 not found) is a hard error
# and falls back to Qwen immediately.
_GEMINI_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

# ─── Cross-modal speaker / face identity (optional) ────────────────────────
# Both modules are OPT-IN. If disabled, or the token/model is missing, the
# pipeline silently proceeds with empty speaker_segments / face_clusters
# (degrades gracefully — the log tells you which env to set).
#
# FACE_IDENTITY: insightface buffalo_l (~300 MB), runs on GPU, all local.
#   * CLIPFORGE_FACE_IDENTITY_ENABLED=true (default) — load and cluster faces.
#   * Set to false to disable on machines without CUDA capability or to save
#     ~1 GB VRAM. The pipeline falls back to anonymous track_ids only.
#
# SPEAKER_DIARIZATION: pyannote/speaker-diarization-community-1 (~150 MB model,
#   CC-BY-4.0, gated on HuggingFace).
#   * CLIPFORGE_DIARIZATION_ENABLED=true and CLIPFORGE_HF_TOKEN set → runs.
#   * Either disabled OR no token → module returns [] silently with a hint.
#   * Acceptance:  https://huggingface.co/pyannote/speaker-diarization-community-1
#     → click "Agree and access repository" (~2 min, automatic approval).
#
# Both stages run SEQUENTIALLY after YOLO unload so we never exceed VRAM.
FACE_IDENTITY_ENABLED = os.getenv("CLIPFORGE_FACE_IDENTITY_ENABLED", "true").lower() == "true"
DIARIZATION_ENABLED = os.getenv("CLIPFORGE_DIARIZATION_ENABLED", "true").lower() == "true"
HF_TOKEN = os.getenv("CLIPFORGE_HF_TOKEN", "")  # required for pyannote diarization

# Internal knobs. Don't expose in .env unless you know what you're doing.
# DBSCAN eps in cosine distance (1-cos similarity: ~0.45 = same person,
# ~0.6 = different ethnicity).
FACE_CLUSTER_EPS = float(os.getenv("CLIPFORGE_FACE_CLUSTER_EPS", "0.45"))
# Minimum samples to form a cluster. Singletons are dropped from the
# cross-modal pass so we don't create fake "Person X" labels for one-off
# faces (a stranger walking through the frame, an inset cameo).
FACE_CLUSTER_MIN_SAMPLES = int(os.getenv("CLIPFORGE_FACE_CLUSTER_MIN_SAMPLES", "2"))

def gemini_is_configured() -> bool:
    """True only when Gemini is enabled AND has an API key + proxy set."""
    return bool(GEMINI_ENABLED and GEMINI_API_KEY and GEMINI_PROXY)