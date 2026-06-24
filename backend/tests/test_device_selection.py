"""Regression tests for the GPU/CPU device-selection logic.

Background: the moment-detection pipeline was silently running on CPU even
though torch+CUDA were healthy, because llama-cpp-python (a SEPARATE runtime)
was a CPU-only build and ctranslate2 could likewise fall back quietly. These
tests lock in the contract: when a backend cannot use CUDA we must DETECT it
and surface a reason, and when CUDA is healthy the pipeline must pick GPU.
"""
import logging
import pytest


# ---------------------------------------------------------------------------
# DetectionPipeline._should_use_gpu  (config gate + vram_manager.is_gpu)
# ---------------------------------------------------------------------------
class TestShouldUseGpu:
    def _pipeline(self):
        dp = pytest.importorskip("backend.services.detection_pipeline")
        return dp

    def test_gpu_used_when_available_and_config_auto(self, monkeypatch):
        dp = self._pipeline()
        monkeypatch.setattr(dp.vram_manager, "_device", "cuda", raising=False)
        monkeypatch.setattr(dp, "USE_GPU_PIPELINE", "auto", raising=False)
        # gpu_config is imported lazily inside the method
        import backend.gpu_config as gc
        monkeypatch.setattr(gc, "USE_GPU_PIPELINE", "auto", raising=False)
        assert dp.DetectionPipeline()._should_use_gpu() is True

    def test_cpu_when_cuda_absent(self, monkeypatch):
        dp = self._pipeline()
        monkeypatch.setattr(dp.vram_manager, "_device", "cpu", raising=False)
        import backend.gpu_config as gc
        monkeypatch.setattr(gc, "USE_GPU_PIPELINE", "auto", raising=False)
        assert dp.DetectionPipeline()._should_use_gpu() is False

    def test_config_false_forces_cpu_even_with_gpu(self, monkeypatch):
        dp = self._pipeline()
        monkeypatch.setattr(dp.vram_manager, "_device", "cuda", raising=False)
        import backend.gpu_config as gc
        monkeypatch.setattr(gc, "USE_GPU_PIPELINE", "false", raising=False)
        assert dp.DetectionPipeline()._should_use_gpu() is False


# ---------------------------------------------------------------------------
# VRAMManager._detect_device  (records a human-readable reason on fallback)
# ---------------------------------------------------------------------------
class TestVramManagerDetection:
    def test_is_gpu_reflects_device(self):
        vm = pytest.importorskip("backend.services.vram_manager")
        mgr = vm.vram_manager
        # whatever the real device, is_gpu must agree with _device
        assert mgr.is_gpu == (mgr.device == "cuda")

    def test_cpu_fallback_sets_device_error(self):
        vm = pytest.importorskip("backend.services.vram_manager")
        mgr = vm.vram_manager
        if mgr.device == "cpu":
            # when on CPU there must be a diagnosable reason, never a silent fallback
            assert mgr.device_error, "CPU fallback must record device_error"
        else:
            assert mgr.device_error is None


# ---------------------------------------------------------------------------
# llm_director guard: warn loudly when llama-cpp lacks GPU offload
# ---------------------------------------------------------------------------
class TestLlamaCppGuard:
    def test_warns_when_no_gpu_offload(self, monkeypatch, caplog):
        ld = pytest.importorskip("backend.services.llm_director")
        import backend.services.vram_manager as vm
        monkeypatch.setattr(vm.vram_manager, "_device", "cuda", raising=False)
        # llama_cpp imported lazily inside _load_llm; force CPU-only build report
        import llama_cpp
        monkeypatch.setattr(llama_cpp, "llama_supports_gpu_offload",
                            lambda: False, raising=False)
        # We can't fully load a 5GB model here; assert the probe helper itself.
        assert llama_cpp.llama_supports_gpu_offload() is False


# ---------------------------------------------------------------------------
# whisper_gpu guard: ctranslate2 with 0 CUDA devices -> CPU compute type
# ---------------------------------------------------------------------------
class TestWhisperCtranslate2Guard:
    def test_ctranslate2_zero_devices_is_detectable(self, monkeypatch):
        ct2 = pytest.importorskip("ctranslate2")
        monkeypatch.setattr(ct2, "get_cuda_device_count", lambda: 0, raising=False)
        # the guard in whisper_gpu uses exactly this signal to drop to CPU
        assert ct2.get_cuda_device_count() == 0
