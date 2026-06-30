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


# --- shared pytest fixtures -------------------------------------------------
import pytest


@pytest.fixture(autouse=True)
def _reset_gemini_health_cache():
    """Wipe the class-level health cache so each test that mocks
    `_build_client` actually triggers a fake HTTP request. Without this,
    a successful test_503_is_retried_then_succeeds() poisons the next
    dozen tests with a stale "OK" cache hit."""
    from backend.services.gemini_director import GeminiDirector
    GeminiDirector._health_cache["ok_at_monotonic"] = None
    yield
    GeminiDirector._health_cache["ok_at_monotonic"] = None


# IDs that we use as test fixtures in `test_accounts.py`. Anything
# outside this list is treated as production data and preserved.
TEST_ACCOUNT_IDS = (
    "anime-ch", "u1", "delme", "ch1", "a", "t1", "ovr-acc",
)


@pytest.fixture(autouse=True, scope="session")
def _purge_test_accounts_at_session_start():
    """Wipe stale `accounts` rows the test suite creates. Runs once per
    `pytest` invocation so cross-test pollution can't break a re-run.

    We never touch the seeded 'default' row — that's a system fallback
    relied on by #3 paths that pass account_id=None.
    """
    import asyncio
    from backend.db import get_db, init_db
    async def _cleanup():
        await init_db()                  # ensure schema/seed exists
        placeholders = ",".join("?" for _ in TEST_ACCOUNT_IDS)
        async with get_db() as db:
            await db.execute(
                f"DELETE FROM accounts WHERE id != 'default' "
                f"AND id IN ({placeholders})",
                TEST_ACCOUNT_IDS,
            )
            await db.commit()
    try:
        asyncio.run(_cleanup())
    except Exception:
        pass
    yield
