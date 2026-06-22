"""LLM Director - Qwen2.5-7B-Instruct GGUF for moment analysis.

GPU-first: loads all layers on GPU when CUDA available.
"""
from __future__ import annotations
import logging
from typing import Optional
from backend.gpu_config import (
    QWEN_MODEL_PATH, QWEN_MODEL_REPO, QWEN_MODEL_FILE,
    QWEN_N_CTX, QWEN_N_GPU_LAYERS, QWEN_TEMPERATURE,
    QWEN_TOP_P, QWEN_PRESENCE_PENALTY
)
from backend.services.vram_manager import vram_manager
from backend.schemas.moment_instruction import DirectorOutput
from backend.services.context_builder import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LLMDirector:
    """Qwen2.5-7B-Instruct Q4_K_M GGUF via llama-cpp-python.
    
    GPU-first: n_gpu_layers=-1 loads all layers on GPU.
    Uses instructor library for structured JSON output.
    """

    def _download_model_if_needed(self) -> None:
        """Download Qwen2.5-7B-Instruct GGUF if not present."""
        if QWEN_MODEL_PATH.exists():
            return
        
        logger.info(f"🧠 [Qwen3] Первая загрузка — скачиваю модель (~4.7 GB), подождите...")
        logger.info("🧠 [Qwen3] Это может занять 5-15 минут в зависимости от скорости интернета...")
        
        try:
            from huggingface_hub import hf_hub_download
            hf_hub_download(
                repo_id=QWEN_MODEL_REPO,
                filename=QWEN_MODEL_FILE,
                local_dir=str(QWEN_MODEL_PATH.parent),
                local_dir_use_symlinks=False,
            )
            logger.info("🧠 [Qwen3] Модель успешно скачана")
        except Exception as e:
            raise RuntimeError(f"Failed to download Qwen model: {e}")

    def analyze(self, context_log: str, user_instructions: str = "") -> DirectorOutput:
        """Analyze video context and generate moment instructions.
        
        Args:
            context_log: Structured text log from Stage 1
            user_instructions: Optional user-provided analysis instructions
            
        Returns:
            DirectorOutput with ranked moments and camera plans
        """
        import instructor
        from llama_cpp import Llama
        import time

        self._download_model_if_needed()

        n_gpu_layers = QWEN_N_GPU_LAYERS if vram_manager.is_gpu else 0
        load_start = time.time()
        logger.info(f"🧠 [Qwen3] Загрузка модели Qwen3-8B Q4_K_M (~4.5 GB VRAM)...")

        def _load():
            return Llama(
                model_path=str(QWEN_MODEL_PATH),
                n_ctx=QWEN_N_CTX,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
            )

        llm = vram_manager.load_model("qwen2.5", _load)
        client = instructor.from_llama_cpp(llm)
        load_time = time.time() - load_start
        logger.info(f"🧠 [Qwen3] Модель загружена за {load_time:.1f}с")
        
        # Calculate token count estimate
        token_count = len(context_log) // 4
        logger.info(f"🧠 [Qwen3] Отправляю контекст (~{token_count} токенов) на анализ...")
        logger.info(f"🧠 [Qwen3] ИИ анализирует содержание...")
        
        analyze_start = time.time()
        result = client.chat.completions.create(
            model="qwen2.5",
            response_model=DirectorOutput,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_log},
            ],
            temperature=QWEN_TEMPERATURE,
            top_p=QWEN_TOP_P,
            presence_penalty=QWEN_PRESENCE_PENALTY,
            max_tokens=4096,
        )
        analyze_time = time.time() - analyze_start
        
        logger.info(f"🧠 [Qwen3] Анализ завершён: выбрано {len(result.moments)} моментов за {analyze_time:.1f}с")
        
        if result.moments:
            top_moment = result.moments[0]
            logger.info(f"🧠 [Qwen3] Топ момент: \"{top_moment.hook}\" (вирусность: {top_moment.virality_score:.0f}/100)")

        vram_manager.unload_model("qwen2.5")
        logger.info(f"🧠 [Qwen3] Модель выгружена из VRAM")
        return result


# Global singleton instance
llm_director = LLMDirector()
