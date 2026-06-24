#!/usr/bin/env python
"""ClipForge GPU diagnostic.

Run from the backend/ directory:
    python diagnose_gpu.py

Prints exactly why the detection pipeline runs on GPU or falls back to CPU.
"""
from __future__ import annotations
import shutil
import subprocess
import sys


def line(label, value):
    print(f"  {label:<28} {value}")


def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_nvidia_smi():
    section("1. NVIDIA driver (nvidia-smi)")
    exe = shutil.which("nvidia-smi")
    if not exe:
        line("nvidia-smi", "NOT FOUND on PATH (no driver, or not installed)")
        return
    try:
        out = subprocess.check_output(
            [exe, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            text=True, timeout=15,
        ).strip()
        line("GPU(s)", out or "(none reported)")
    except Exception as e:
        line("nvidia-smi error", f"{type(e).__name__}: {e}")


def check_torch():
    section("2. PyTorch / CUDA")
    try:
        import torch
    except Exception as e:
        line("torch", f"IMPORT FAILED: {type(e).__name__}: {e}")
        return
    build = torch.__version__
    line("torch version", build)
    line("CPU-only build?", "YES  <-- this forces CPU" if "+cpu" in build else "no")
    avail = torch.cuda.is_available()
    line("cuda.is_available()", avail)
    line("torch arch list", getattr(torch.cuda, "get_arch_list", lambda: "?")() if avail else "n/a")
    if avail:
        try:
            cap = torch.cuda.get_device_capability(0)
            sm = f"sm_{cap[0]}{cap[1]}"
            line("device name", torch.cuda.get_device_name(0))
            line("compute capability", f"{sm}  (sm_120 = Blackwell / RTX 50xx)")
            supported = list(torch.cuda.get_arch_list())
            if supported and sm not in supported:
                line("!! MISMATCH", f"{sm} not in {supported} -> kernels fail, CPU fallback")
            # actually try a kernel launch to prove usability
            try:
                x = torch.zeros(8, device="cuda")
                _ = (x + 1).sum().item()
                line("kernel launch test", "OK (GPU usable)")
            except Exception as e:
                line("kernel launch test", f"FAILED: {type(e).__name__}: {e}")
        except Exception as e:
            line("device probe error", f"{type(e).__name__}: {e}")


def check_faster_whisper():
    section("3. faster-whisper / ctranslate2 (transcription)")
    try:
        import ctranslate2
        line("ctranslate2", ctranslate2.__version__)
        try:
            count = ctranslate2.get_cuda_device_count()
            line("ct2 CUDA devices", count)
            if count == 0:
                line("note", "ct2 sees no CUDA -> Whisper runs int8 on CPU")
        except Exception as e:
            line("ct2 cuda probe", f"{type(e).__name__}: {e}")
    except Exception as e:
        line("ctranslate2", f"not importable: {type(e).__name__}: {e}")


def check_ffmpeg_nvenc():
    section("4. ffmpeg NVENC (GPU encode)")
    exe = shutil.which("ffmpeg")
    if not exe:
        line("ffmpeg", "NOT FOUND on PATH")
        return
    try:
        out = subprocess.check_output([exe, "-hide_banner", "-encoders"], text=True, stderr=subprocess.STDOUT, timeout=15)
        line("h264_nvenc", "available" if "h264_nvenc" in out else "MISSING (CPU x264 only)")
    except Exception as e:
        line("ffmpeg error", f"{type(e).__name__}: {e}")


def check_llama_cpp():
    section("3b. llama-cpp-python (LLM Director - the heavy stage)")
    try:
        from llama_cpp import llama_cpp as _ll
    except Exception as e:
        line("llama_cpp", f"not importable: {type(e).__name__}: {e}")
        return
    # llama-cpp exposes build flags; a CPU-only wheel silently ignores n_gpu_layers
    supports = None
    for fn in ("llama_supports_gpu_offload",):
        f = getattr(_ll, fn, None)
        if callable(f):
            try:
                supports = bool(f())
            except Exception:
                supports = None
    if supports is None:
        line("GPU offload support", "unknown (old llama-cpp) - load with verbose=True to confirm")
    elif supports:
        line("GPU offload support", "YES (CUDA build) - n_gpu_layers will be honored")
    else:
        line("GPU offload support", "NO  <-- CPU-only build! n_gpu_layers IGNORED -> LLM runs on CPU")
        line("fix", "reinstall: set CMAKE_ARGS=-DGGML_CUDA=on && pip install --force-reinstall --no-cache-dir llama-cpp-python")


def check_free_vram():
    section("4b. Free VRAM (models need ~8 GB: Whisper ~3 + Qwen ~5)")
    try:
        import torch
        if not torch.cuda.is_available():
            line("free VRAM", "n/a (no CUDA)")
            return
        free, total = torch.cuda.mem_get_info(0)
        gb = 1024 ** 3
        line("total VRAM", f"{total/gb:.1f} GB")
        line("free VRAM", f"{free/gb:.1f} GB")
        if free / gb < 6.5:
            line("!! WARNING", "less than ~6.5 GB free - models may OOM or fall back to CPU.")
            line("fix", "close GPU-heavy apps (games, Discord, browsers) to free VRAM.")
    except Exception as e:
        line("free VRAM error", f"{type(e).__name__}: {e}")


def check_vram_manager():
    section("5. What ClipForge actually selects")
    try:
        from services.vram_manager import vram_manager
        line("selected device", vram_manager.device)
        line("is_gpu", vram_manager.is_gpu)
        line("device_error", vram_manager.device_error or "(none - on GPU)")
    except Exception as e:
        line("vram_manager error", f"{type(e).__name__}: {e}")
        print("    (run this script from the backend/ directory)")


def main():
    print("ClipForge GPU diagnostic")
    print(f"python: {sys.version.split()[0]}  ({sys.executable})")
    check_nvidia_smi()
    check_torch()
    check_faster_whisper()
    check_llama_cpp()
    check_ffmpeg_nvenc()
    check_free_vram()
    check_vram_manager()
    section("Summary")
    print("  If device_error is set, that line is the root cause of CPU usage.")
    print("  Most common fix (Blackwell/RTX 50xx): reinstall torch with CUDA 12.8+:")
    print("    pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu128")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())