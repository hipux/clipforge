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
FACE_SAMPLE_FPS = float(os.getenv("CLIPFORGE_FACE_SAMPLE_FPS", "2.0"))
FACE_CONFIDENCE_THRESHOLD = float(os.getenv("CLIPFORGE_FACE_CONF", "0.5"))

# ─── LLM Configuration (Qwen3-8B GGUF) ─────────────────────────────────────
QWEN_MODEL_REPO = "Qwen/Qwen3-8B-GGUF"
QWEN_MODEL_FILE = "qwen3-8b-q4_k_m.gguf"
QWEN_MODEL_PATH = MODELS_DIR / QWEN_MODEL_FILE
QWEN_N_CTX = int(os.getenv("CLIPFORGE_QWEN_N_CTX", "8192"))
QWEN_N_GPU_LAYERS = int(os.getenv("CLIPFORGE_QWEN_N_GPU_LAYERS", "-1"))  # -1 = all layers on GPU
QWEN_TEMPERATURE = float(os.getenv("CLIPFORGE_QWEN_TEMP", "0.3"))
QWEN_PRESENCE_PENALTY = float(os.getenv("CLIPFORGE_QWEN_PRESENCE", "1.5"))
QWEN_TOP_P = float(os.getenv("CLIPFORGE_QWEN_TOP_P", "0.95"))

# ─── NVENC Encoder Configuration ───────────────────────────────────────────
NVENC_PRESET = os.getenv("CLIPFORGE_NVENC_PRESET", "p7")
NVENC_CQ = int(os.getenv("CLIPFORGE_NVENC_CQ", "20"))
NVENC_RC_LOOKAHEAD = int(os.getenv("CLIPFORGE_NVENC_LOOKAHEAD", "20"))

# ─── Pipeline Mode ─────────────────────────────────────────────────────────
# GPU-first: "true" (default) = use GPU if CUDA available
#            "false" = force CPU legacy pipeline
#            "auto" = same as "true"
USE_GPU_PIPELINE = os.getenv("CLIPFORGE_USE_GPU", "true")
VRAM_SAFETY_MARGIN_GB = float(os.getenv("CLIPFORGE_VRAM_MARGIN", "0.5"))
