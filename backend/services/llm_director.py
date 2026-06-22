"""LLM Director - Qwen3-8B GGUF for moment analysis.

GPU-first: loads all layers on GPU when CUDA available.
"""
from __future__ import annotations
import logging
import time
import requests
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
    """Qwen3-8B Q4_K_M GGUF via llama-cpp-python.
    
    GPU-first: n_gpu_layers=-1 loads all layers on GPU.
    Uses instructor library for structured JSON output.
    """

    def _download_model_if_needed(self) -> None:
        """Download Qwen3-8B GGUF if not present.
        
        Uses requests library directly to avoid httpx/huggingface_hub client closure issues.
        """
        # Check if model exists and has reasonable size (> 1 GB)
        if QWEN_MODEL_PATH.exists() and QWEN_MODEL_PATH.stat().st_size > 1_000_000_000:
            logger.info(f"🧠 [Qwen3] Модель найдена: {QWEN_MODEL_PATH}")
            return
        
        logger.info(f"🧠 [Qwen3] Первая загрузка — скачиваю модель (~4.7 GB), подождите...")
        logger.info("🧠 [Qwen3] Это может занять 5-15 минут в зависимости от скорости интернета...")
        
        try:
            # Direct download via requests to avoid httpx client issues
            url = f"https://huggingface.co/{QWEN_MODEL_REPO}/resolve/main/{QWEN_MODEL_FILE}"
            QWEN_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Stream download with progress logging
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                downloaded = 0
                last_log_percent = 0
                
                with open(QWEN_MODEL_PATH, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192 * 1024):  # 8MB chunks
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Log progress every 10%
                            if total:
                                pct = downloaded / total * 100
                                if int(pct / 10) > int(last_log_percent / 10):
                                    logger.info(
                                        f"🧠 [Qwen3] Скачано: {pct:.0f}% "
                                        f"({downloaded/1e9:.1f}/{total/1e9:.1f} GB)"
                                    )
                                    last_log_percent = pct
            
            logger.info("🧠 [Qwen3] Модель успешно скачана")
        except Exception as e:
            # Clean up partial download
            if QWEN_MODEL_PATH.exists():
                QWEN_MODEL_PATH.unlink()
            raise RuntimeError(f"Failed to download Qwen model: {e}")

    def analyze(
        self,
        context_log_or_chunks: str | list[str],
        user_instructions: str = ""
    ) -> DirectorOutput:
        """Analyze video context and generate moment instructions.
        
        Supports both single context string and chunked analysis for long videos.
        
        Args:
            context_log_or_chunks: Either a single context string or list of chunk strings
            user_instructions: Optional user instructions for the LLM
            
        Returns:
            DirectorOutput with moment candidates
        """
        from llama_cpp import Llama
        import instructor
        
        # Download model if needed (first run only)
        self._download_model_if_needed()
        
        # Determine device/layers
        n_gpu_layers = QWEN_N_GPU_LAYERS if vram_manager.device == "cuda" else 0
        device_str = "GPU (все слои)" if n_gpu_layers == -1 else f"GPU ({n_gpu_layers} слоёв)" if n_gpu_layers > 0 else "CPU"
        
        load_start = time.time()
        logger.info(f"🧠 [Qwen3] Загрузка модели (~4.5 GB VRAM, {device_str})...")
        
        def _load_llm():
            return Llama(
                model_path=str(QWEN_MODEL_PATH),
                n_gpu_layers=n_gpu_layers,
                n_ctx=QWEN_N_CTX,
                chat_format="qwen2",
                verbose=False,
            )
        
        llm = vram_manager.load_model("llm", _load_llm)
        load_time = time.time() - load_start
        logger.info(f"🧠 [Qwen3] Модель загружена за {load_time:.1f}с")
        
        # Create instructor client
        client = instructor.from_llama_cpp(llm)
        
        # Handle chunked vs single analysis
        if isinstance(context_log_or_chunks, list):
            return self._analyze_chunked(client, context_log_or_chunks, user_instructions)
        else:
            return self._analyze_single(client, context_log_or_chunks, user_instructions)

    def _analyze_single(
        self,
        client,
        context_log: str,
        user_instructions: str
    ) -> DirectorOutput:
        """Single-pass LLM analysis for videos that fit in context window."""
        logger.info(f"🧠 [Qwen3] Анализирую контекст ({len(context_log)} символов)...")
        
        analyze_start = time.time()
        
        system_prompt_filled = SYSTEM_PROMPT.format(user_instructions=user_instructions or "Нет")
        
        try:
            result = client.chat.completions.create(
                model="qwen3",
                response_model=DirectorOutput,
                messages=[
                    {"role": "system", "content": system_prompt_filled},
                    {"role": "user", "content": context_log},
                ],
                temperature=QWEN_TEMPERATURE,
                top_p=QWEN_TOP_P,
                presence_penalty=QWEN_PRESENCE_PENALTY,
                max_tokens=4096,
                max_retries=3,
            )
            
            analyze_time = time.time() - analyze_start
            logger.info(f"🧠 [Qwen3] Анализ завершён за {analyze_time:.1f}с: найдено {len(result.moments)} моментов")
            
            vram_manager.unload_model("llm")
            logger.info("🧠 [Qwen3] Модель выгружена из VRAM")
            
            return result
            
        except Exception as e:
            logger.error(f"🧠 [Qwen3] Ошибка при анализе: {e}")
            vram_manager.unload_model("llm")
            raise

    def _analyze_chunked(
        self,
        client,
        chunks: list[str],
        user_instructions: str
    ) -> DirectorOutput:
        """Multi-pass analysis for long videos split into chunks.
        
        Each chunk is analyzed independently, then results are consolidated.
        """
        logger.info(f"🧠 [Qwen3] Режим chunks: анализирую {len(chunks)} частей...")
        
        all_candidates = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"🧠 [Qwen3] Обрабатываю chunk {i+1}/{len(chunks)} ({len(chunk)} символов)...")
            
            chunk_start = time.time()
            system_prompt = SYSTEM_PROMPT.format(user_instructions=user_instructions or "Нет")
            
            try:
                chunk_result = client.chat.completions.create(
                    model="qwen3",
                    response_model=DirectorOutput,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk},
                    ],
                    temperature=QWEN_TEMPERATURE,
                    top_p=QWEN_TOP_P,
                    presence_penalty=QWEN_PRESENCE_PENALTY,
                    max_tokens=3072,
                    max_retries=2,
                )
                
                chunk_time = time.time() - chunk_start
                logger.info(
                    f"🧠 [Qwen3] Chunk {i+1}/{len(chunks)} за {chunk_time:.1f}с: "
                    f"{len(chunk_result.moments)} моментов"
                )
                all_candidates.extend(chunk_result.moments)
                
            except Exception as e:
                logger.error(f"🧠 [Qwen3] Ошибка в chunk {i+1}: {e}")
                continue
        
        # Consolidate all candidates
        logger.info(f"🧠 [Qwen3] Консолидирую {len(all_candidates)} кандидатов...")
        final_result = self._consolidate_moments(client, all_candidates)
        
        vram_manager.unload_model("llm")
        logger.info("🧠 [Qwen3] Модель выгружена из VRAM")
        
        return final_result

    def _consolidate_moments(self, client, candidates: list) -> DirectorOutput:
        """Consolidate and rank moment candidates from all chunks.
        
        Removes duplicates/overlaps and selects top moments.
        """
        # Build summary of all candidates for consolidation prompt
        summary_lines = ["=== ALL MOMENT CANDIDATES ==="]
        summary_lines.append(f"Total: {len(candidates)} candidates from all chunks")
        summary_lines.append("")
        
        for i, m in enumerate(candidates):
            summary_lines.append(
                f"{i+1}. [{m.start:.1f}s-{m.end:.1f}s] "
                f"virality={m.virality_score:.0f} "
                f"type={m.content_type} "
                f"hook=\"{m.hook}\""
            )
        
        summary_text = "\n".join(summary_lines)
        
        consolidation_prompt = f"""You are reviewing all moment candidates from a multi-chunk analysis.

Your task:
1. Remove duplicates or overlapping moments (keep the one with highest virality)
2. Select the top 5-10 BEST moments overall
3. Rank them by viral potential

RULES:
- Two moments overlap if their time ranges intersect by >50%
- Prefer moments with higher virality_score
- Ensure diversity in content_type
- Return JSON matching DirectorOutput schema

{summary_text}"""
        
        consolidate_start = time.time()
        
        result = client.chat.completions.create(
            model="qwen3",
            response_model=DirectorOutput,
            messages=[
                {"role": "system", "content": "You are a viral video editor consolidating moment candidates."},
                {"role": "user", "content": consolidation_prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        
        consolidate_time = time.time() - consolidate_start
        logger.info(f"🧠 [Qwen3] Консолидация за {consolidate_time:.1f}с: {len(candidates)} → {len(result.moments)} моментов")
        
        return result


# Global singleton instance
llm_director = LLMDirector()
