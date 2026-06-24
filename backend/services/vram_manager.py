"""VRAM manager for GPU pipeline - singleton pattern."""
from __future__ import annotations
import gc
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class VRAMManager:
    """Singleton VRAM manager. GPU-first: always CUDA if available.
    
    Manages model loading/unloading lifecycle to maximize VRAM efficiency.
    Each stage loads its models, uses them, then unloads before next stage.
    """

    _instance: Optional["VRAMManager"] = None
    _loaded_models: Dict[str, Any]
    _device: str
    _device_error: Optional[str]

    def __new__(cls) -> "VRAMManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded_models = {}
            cls._instance._device = cls._instance._detect_device()
        return cls._instance

    def _detect_device(self) -> str:
        """Detect GPU availability and log device info.

        On failure the REAL reason is logged at WARNING level (previously it was
        swallowed at debug), so CPU fallbacks are diagnosable. The reason is also
        stored on self._device_error for the /api/gpu endpoint and diagnostics.
        """
        self._device_error = None
        try:
            import torch
        except Exception as e:  # torch missing / broken install
            self._device_error = f"PyTorch import failed: {type(e).__name__}: {e}"
            logger.warning(f"CUDA unavailable - {self._device_error} -> CPU legacy pipeline")
            return "cpu"

        try:
            if not torch.cuda.is_available():
                build = getattr(torch, "__version__", "?")
                if "+cpu" in build:
                    reason = "PyTorch is a CPU-only build (reinstall with a CUDA wheel)"
                else:
                    reason = "torch.cuda.is_available() is False (NVIDIA driver / CUDA runtime missing or mismatched)"
                self._device_error = f"{reason} (torch {build})"
                logger.warning(f"CUDA unavailable - {self._device_error} -> CPU legacy pipeline")
                return "cpu"

            name = torch.cuda.get_device_name(0)
            cap = torch.cuda.get_device_capability(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            sm = f"sm_{cap[0]}{cap[1]}"

            # CUDA can be available yet unusable if the installed torch was not
            # built with kernels for this compute capability. Classic case:
            # RTX 5060 (Blackwell, sm_120) on a torch built only up to sm_90 ->
            # every kernel launch errors and the app silently runs on CPU.
            try:
                supported = list(torch.cuda.get_arch_list())
            except Exception:
                supported = []
            if supported and sm not in supported:
                self._device_error = (
                    f"GPU {name} is {sm} but installed torch only supports {supported}. "
                    f"Install a torch build with {sm} kernels (e.g. CUDA 12.8+ for Blackwell)."
                )
                logger.warning(f"CUDA present but unusable - {self._device_error} -> CPU legacy pipeline")
                return "cpu"

            logger.info(f"GPU detected: {name} (compute {sm}, {vram:.1f} GB VRAM) - GPU-first pipeline active")
            return "cuda"
        except Exception as e:
            self._device_error = f"{type(e).__name__}: {e}"
            logger.warning(f"CUDA detection raised - {self._device_error} -> CPU legacy pipeline", exc_info=True)
            return "cpu"

    @property
    def device(self) -> str:
        """Current device: 'cuda' or 'cpu'."""
        return self._device

    @property
    def is_gpu(self) -> bool:
        """True if GPU is available and active."""
        return self._device == "cuda"

    @property
    def device_error(self) -> Optional[str]:
        """Human-readable reason the GPU was not used, or None if on GPU."""
        return getattr(self, "_device_error", None)

    def load_model(self, name: str, loader: Callable[[], Any]) -> Any:
        """Load a model with given name using loader function.
        
        Args:
            name: Model identifier (e.g., 'whisper', 'face', 'qwen3')
            loader: Function that loads and returns the model
            
        Returns:
            Loaded model instance
        """
        if name not in self._loaded_models:
            logger.info(f"Loading model: {name} on {self._device}")
            self._loaded_models[name] = loader()
            if self.is_gpu:
                self._log_vram(f"after loading {name}")
        return self._loaded_models[name]

    def unload_model(self, name: str) -> None:
        """Unload a specific model and free VRAM."""
        if name in self._loaded_models:
            logger.info(f"Unloading model: {name}")
            del self._loaded_models[name]
            self._flush_gpu()

    def unload_all(self) -> None:
        """Unload ALL models and aggressively flush VRAM."""
        names = list(self._loaded_models.keys())
        for name in names:
            del self._loaded_models[name]
        self._loaded_models.clear()
        self._flush_gpu()
        logger.info("All models unloaded, VRAM cleared")

    def _flush_gpu(self) -> None:
        """Triple flush: GC + empty_cache + synchronize."""
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except (ImportError, Exception):
            pass

    def get_vram_usage(self) -> dict:
        """Get current VRAM usage statistics.
        
        Returns:
            Dict with allocated_gb, reserved_gb, total_gb, free_gb
        """
        try:
            import torch
            if torch.cuda.is_available():
                # mem_get_info() = driver-level (free, total) for the WHOLE device.
                # Whisper(ctranslate2) & LLM(llama-cpp) allocate outside torch's allocator,
                # so memory_allocated() froze the UI at the pre-load value. This sees all.
                free_b, total_b = torch.cuda.mem_get_info(0)
                free = free_b / 1024**3
                used = (total_b - free_b) / 1024**3
                allocated = used
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                return {
                    "allocated_gb": round(allocated, 2),
                    "reserved_gb": round(reserved, 2),
                    "total_gb": round(total, 2),
                    "free_gb": round(free, 2),
                }
        except (ImportError, Exception):
            pass
        return {"allocated_gb": 0, "reserved_gb": 0, "total_gb": 0, "free_gb": 0}

    def _log_vram(self, label: str) -> None:
        """Log VRAM usage with custom label."""
        usage = self.get_vram_usage()
        logger.info(f"VRAM {label}: {usage['allocated_gb']:.2f} GB allocated / {usage['total_gb']:.2f} GB total")
    
    def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded model names."""
        return list(self._loaded_models.keys())


# Global singleton instance
vram_manager = VRAMManager()