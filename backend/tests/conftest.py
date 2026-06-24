"""Pytest fixtures for ClipForge detection tests.

Adds the repo root to sys.path so `import backend.*` works, and installs
lightweight STUBS for heavy native deps (cv2, librosa, faster_whisper,
llama_cpp, torch, scipy) ONLY when they are not importable.

On the real GPU machine these libs are installed, so the stubs are skipped and
tests run against the real code. In a minimal CI/dev box the stubs let the
pure-logic tests import the modules without the native wheels.
"""
import sys
import types
import importlib.util
from pathlib import Path

# --- make 'backend' a top-level importable package -------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]   # .../clipforge
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _missing(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except Exception:
        return True


def _stub(name: str, attrs: dict | None = None) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# --- cv2 -------------------------------------------------------------------
if _missing("cv2"):
    _stub("cv2", {
        "VideoCapture": lambda *a, **k: None,
        "cvtColor": lambda *a, **k: None,
        "resize": lambda *a, **k: None,
        "absdiff": lambda *a, **k: None,
        "COLOR_BGR2GRAY": 0, "CAP_PROP_FPS": 5,
    })

# --- librosa ---------------------------------------------------------------
if _missing("librosa"):
    lb = _stub("librosa", {"load": lambda *a, **k: ([], 22050)})
    lb.feature = types.SimpleNamespace(rms=lambda *a, **k: [[]])
    lb.onset = types.SimpleNamespace(onset_detect=lambda *a, **k: [])
    lb.frames_to_time = lambda *a, **k: []

# --- faster_whisper --------------------------------------------------------
if _missing("faster_whisper"):
    _stub("faster_whisper", {"WhisperModel": object})

# --- llama_cpp -------------------------------------------------------------
if _missing("llama_cpp"):
    _stub("llama_cpp", {
        "Llama": object,
        "llama_supports_gpu_offload": lambda: False,
    })

# --- torch -----------------------------------------------------------------
if _missing("torch"):
    cuda_ns = types.SimpleNamespace(
        is_available=lambda: False,
        get_device_capability=lambda *a, **k: (0, 0),
        mem_get_info=lambda *a, **k: (0, 0),
    )
    _stub("torch", {"cuda": cuda_ns})

# --- scipy / scipy.signal --------------------------------------------------
if _missing("scipy"):
    sp = _stub("scipy")
    sig = _stub("scipy.signal", {"find_peaks": lambda *a, **k: ([], {})})
    sp.signal = sig
