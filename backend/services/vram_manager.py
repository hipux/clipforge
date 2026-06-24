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

    def __new__(cls) -> "VRAMManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded_models = {}
            cls._instance._device = cls._instance._detect_device()
        return cls._instance

    def _detect_device(self) -> str:
        """Detect GPU availability and log device info."""
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"GPU detected: {name} ({vram:.1f} GB VRAM) — GPU-first pipeline active")
                return "cuda"
        except (ImportError, Exception) as e:
            logger.debug(f"CUDA detection failed: {e}")
        logger.warning("CUDA not available — fallback to CPU legacy pipeline")
        return "cpu"

    @property
    def device(self) -> str:
        """Current device: 'cuda' or 'cpu'."""
        return self._device

    @property
    def is_gpu(self) -> bool:
        """True if GPU is available and active."""
        return self._device == "cuda"

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
        # Try pynvml first — sees ALL VRAM users (CTranslate2, YOLO, PyTorch, etc.)
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_gb = mem.total / (1024**3)
            used_gb = mem.used / (1024**3)
            free_gb = mem.free / (1024**3)
            pynvml.nvmlShutdown()
            return {
                "allocated_gb": round(used_gb, 2),
                "reserved_gb": round(used_gb, 2),
                "total_gb": round(total_gb, 2),
                "free_gb": round(free_gb, 2),
            }
        except Exception:
            pass
        # Fallback: PyTorch (only sees PyTorch tensors, but better than nothing)
        try:
            import torch
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                free = total - reserved
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
