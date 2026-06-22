"""LLM Director - Qwen3-8B GGUF for moment analysis.

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
    """Qwen3-8B Q4_K_M GGUF via llama-cpp-python.
    
    GPU-first: n_gpu_layers=-1 loads all layers on GPU.
    Uses instructor library for structured JSON output.
    """

    def _download_model_if_needed(self) -> None:
        """Download Qwen3-8B GGUF if not present."""
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

    def analyze(
        self,
        context_log_or_chunks: str | list[str],
        user_instructions: str = ""
    ) -> DirectorOutput:
        """Analyze video context and generate moment instructions.
        
        Supports both single context string and list of chunks for long videos.
        For multi-chunk mode, runs LLM on each chunk separately, then consolidates.
        
        Args:
            context_log_or_chunks: Single context string OR list of chunk strings
            user_instructions: Optional user-provided analysis instructions
            
        Returns:
            DirectorOutput with ranked moments and camera plans
        """
        import instructor
        from llama_cpp import Llama
        import time

        self._download_model_if_needed()

        # Determine if we're in chunked mode
        is_chunked = isinstance(context_log_or_chunks, list)
        chunks = context_log_or_chunks if is_chunked else [context_log_or_chunks]
        
        # Load model once for all chunks
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

        llm = vram_manager.load_model("qwen3", _load)
        client = instructor.from_llama_cpp(llm)
        load_time = time.time() - load_start
        logger.info(f"🧠 [Qwen3] Модель загружена за {load_time:.1f}с")
        
        if is_chunked:
            logger.info(f"🧠 [Qwen3] Режим чанков: анализирую {len(chunks)} частей...")
        
        # Analyze each chunk
        all_candidates = []
        total_analyze_time = 0.0
        
        for i, chunk_log in enumerate(chunks):
            chunk_num = i + 1
            token_count = len(chunk_log) // 4
            
            if is_chunked:
                # Extract time window from chunk header
                import re
                match = re.search(r'TIME WINDOW: (\d+\.\d+)s - (\d+\.\d+)s \((\d+\.\d+) - (\d+\.\d+)', chunk_log)
                time_range = f"{match.group(3)}-{match.group(4)} мин" if match else "?"
                logger.info(f"🧠 [Qwen3] Анализирую чанк {chunk_num}/{len(chunks)} ({time_range})...")
            else:
                logger.info(f"🧠 [Qwen3] Отправляю контекст (~{token_count} токенов) на анализ...")
                logger.info(f"🧠 [Qwen3] ИИ анализирует содержание...")
            
            analyze_start = time.time()
            chunk_result = client.chat.completions.create(
                model="qwen3",
                response_model=DirectorOutput,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": chunk_log},
                ],
                temperature=QWEN_TEMPERATURE,
                top_p=QWEN_TOP_P,
                presence_penalty=QWEN_PRESENCE_PENALTY,
                max_tokens=4096,
            )
            analyze_time = time.time() - analyze_start
            total_analyze_time += analyze_time
            
            all_candidates.extend(chunk_result.moments)
            logger.info(f"🧠 [Qwen3] Чанк {chunk_num}/{len(chunks)} обработан: {len(chunk_result.moments)} кандидатов за {analyze_time:.1f}с")
        
        # Consolidation pass for multi-chunk mode
        if is_chunked and len(all_candidates) > 10:
            logger.info(f"🧠 [Qwen3] Консолидация: {len(all_candidates)} кандидатов → финальный ранкинг...")
            final_result = self._consolidate_candidates(client, all_candidates)
        elif is_chunked:
            # Few candidates, just sort by virality
            sorted_moments = sorted(all_candidates, key=lambda m: m.virality_score, reverse=True)
            final_result = DirectorOutput(
                moments=sorted_moments,
                total_analyzed=len(all_candidates),
                language_detected="ru"
            )
            logger.info(f"🧠 [Qwen3] Мало кандидатов, консолидация не нужна")
        else:
            # Single chunk mode, use result directly
            final_result = DirectorOutput(
                moments=all_candidates,
                total_analyzed=len(all_candidates),
                language_detected="ru"
            )
        
        logger.info(f"🧠 [Qwen3] Анализ завершён: выбрано {len(final_result.moments)} моментов за {total_analyze_time:.1f}с")
        
        if final_result.moments:
            top_moment = final_result.moments[0]
            logger.info(f"🧠 [Qwen3] Топ момент: \"{top_moment.hook}\" (вирусность: {top_moment.virality_score:.0f}/100)")

        vram_manager.unload_model("qwen3")
        logger.info(f"🧠 [Qwen3] Модель выгружена из VRAM")
        return final_result

    def _consolidate_candidates(self, client, candidates: list) -> DirectorOutput:
        """Run final consolidation pass to rank and deduplicate candidates.
        
        Args:
            client: instructor client
            candidates: List of MomentInstruction from all chunks
            
        Returns:
            DirectorOutput with final ranked moments
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
        
        import time
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
