"""LLM Director - Qwen3-8B GGUF for moment analysis.

GPU-first: loads all layers on GPU when CUDA available.
"""
from __future__ import annotations
import logging
import re
import time
import requests
from typing import Optional, Callable
from backend.gpu_config import (
    QWEN_MODEL_PATH, QWEN_MODEL_REPO, QWEN_MODEL_FILE,
    QWEN_N_CTX, QWEN_N_GPU_LAYERS, QWEN_TEMPERATURE,
    QWEN_TOP_P, QWEN_PRESENCE_PENALTY
)
from backend.services.vram_manager import vram_manager
from backend.schemas.moment_instruction import DirectorOutput
from backend.services.context_builder import build_system_prompt

# Try to import huggingface_hub for robust model downloads (handles auth, resumable, case-sensitive filenames)
try:
    from huggingface_hub import hf_hub_download as _hf_hub_download
    _HF_HUB_AVAILABLE = True
except ImportError:
    _HF_HUB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Regex to strip Qwen3 thinking blocks before JSON parsing.
# Qwen3 thinking mode emits <think>...</think> before the JSON — pydantic
# cannot parse JSON starting with '<', so we intercept and strip it here.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks and ```json fences from Qwen3 responses."""
    text = _THINK_RE.sub("", text).strip()
    # Qwen often wraps JSON in a markdown code fence; extract the fenced body.
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if m:
            text = m.group(1)
    return text.strip()



class LLMDirector:
    """Qwen3-8B Q4_K_M GGUF via llama-cpp-python.
    
    GPU-first: n_gpu_layers=-1 loads all layers on GPU.
    Uses instructor library for structured JSON output.
    Qwen3 thinking mode is ENABLED: <think> blocks stripped transparently before
    pydantic validation for best reasoning quality.
    """

    def _download_model_if_needed(self):
        """Download Qwen3 GGUF model if not present.
        
        Two-stage download:
        1. Try huggingface_hub (preferred, handles case-sensitivity + resumable)
        2. Fallback to direct download via requests (legacy)
        """
        if QWEN_MODEL_PATH.exists():
            file_size_gb = QWEN_MODEL_PATH.stat().st_size / (1024**3)
            logger.info(f"🧠 [Qwen3] Модель найдена: {QWEN_MODEL_PATH} ({file_size_gb:.2f} GB)")
            return
        
        logger.info("🧠 [Qwen3] Первая загрузка — скачиваю модель (~4.7 GB), подождите...")
        logger.info("🧠 [Qwen3] Это может занять 5-15 минут в зависимости от скорости интернета...")
        
        QWEN_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Stage 1: Try huggingface_hub (preferred method)
        if _HF_HUB_AVAILABLE:
            try:
                logger.info("🧠 [Qwen3] Downloading via huggingface_hub (primary method)...")
                downloaded_path = _hf_hub_download(
                    repo_id=QWEN_MODEL_REPO,
                    filename=QWEN_MODEL_FILE,
                    local_dir=str(QWEN_MODEL_PATH.parent),
                    local_dir_use_symlinks=False,
                )
                logger.info(f"🧠 [Qwen3] ✓ Модель загружена через huggingface_hub")
                return
            except Exception as e:
                logger.warning(f"🧠 [Qwen3] huggingface_hub failed: {e}, trying direct download...")
        
        # Stage 2: Fallback to direct download
        try:
            url = f"https://huggingface.co/{QWEN_MODEL_REPO}/resolve/main/{QWEN_MODEL_FILE}"
            r = requests.get(url, stream=True, timeout=600)
            r.raise_for_status()
            
            total_size = int(r.headers.get('content-length', 0))
            
            with open(QWEN_MODEL_PATH, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress_pct = (downloaded / total_size * 100) if total_size else 0
                        if downloaded % (50 * 1024 * 1024) < 8192:  # Log every ~50MB
                            logger.info(f"🧠 [Qwen3] Загрузка: {progress_pct:.1f}% ({downloaded / (1024**3):.2f} GB)")
            
            logger.info("🧠 [Qwen3] ✓ Модель успешно загружена")
            
        except Exception as e:
            raise RuntimeError(f"Failed to download Qwen model: {e}")

    def _call_with_thinking(self, create_fn, **kwargs) -> DirectorOutput:
        """Call instructor and strip <think> blocks from Qwen3 response.

        Qwen3 in thinking mode emits:
            <think>...reasoning...</think>\n{...json...}

        We call without response_model to get raw text, strip the think block,
        then validate the clean JSON with pydantic manually.
        """
        response_model = kwargs.pop("response_model")
        kwargs.pop("max_retries", None)  # raw call: no instructor retry

        # Get raw completion (no structured parsing yet)
        raw = create_fn(response_model=None, **kwargs)

        # Extract content string
        if hasattr(raw, "choices") and raw.choices:
            content_text = raw.choices[0].message.content or ""
        else:
            content_text = str(raw)

        # Log thinking block presence
        think_match = _THINK_RE.search(content_text)
        if think_match:
            think_len = len(think_match.group(0))
            logger.debug(f"🧠 [Qwen3] <think> блок: {think_len} символов → удалён перед парсингом")

        # Strip think blocks and validate JSON
        stripped = _strip_think(content_text)
        return response_model.model_validate_json(stripped)

    def analyze(
        self,
        context_log_or_chunks: str | list[str],
        user_instructions: str = "",
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        min_duration: int = 60,
        max_duration: int = 90,
        max_moments: int = 15,
    ) -> DirectorOutput:
        """Analyze video context and generate moment instructions.
        
        Supports both single context string and chunked analysis for long videos.
        
        Args:
            context_log_or_chunks: Either a single context string or list of chunk strings
            user_instructions: Optional user instructions for the LLM
            on_progress: Optional callback(chunk_i, total, phase) for progress updates
            
        Returns:
            DirectorOutput with moment candidates
        """
        from llama_cpp import Llama
        import instructor
        
        # Download model if needed (first run only)
        self._download_model_if_needed()
        
        # Determine device/layers
        n_gpu_layers = QWEN_N_GPU_LAYERS if vram_manager.device == "cuda" else 0

        # Guard: llama-cpp-python is a SEPARATE runtime from torch. A CPU-only
        # wheel silently IGNORES n_gpu_layers and runs the LLM on CPU with NO
        # error -> the slowest stage quietly runs on CPU. Surface it loudly.
        if vram_manager.device == "cuda":
            try:
                from llama_cpp import llama_supports_gpu_offload
                if not llama_supports_gpu_offload():
                    logger.warning(
                        "[Qwen3] llama-cpp-python was built WITHOUT CUDA -> "
                        "n_gpu_layers ignored, LLM runs on CPU (very slow). Reinstall: "
                        "set CMAKE_ARGS=-DGGML_CUDA=on && pip install --force-reinstall "
                        "--no-cache-dir llama-cpp-python"
                    )
            except Exception:
                logger.debug("[Qwen3] could not probe llama-cpp GPU support")
        device_str = "GPU (все слои)" if n_gpu_layers == -1 else f"GPU ({n_gpu_layers} слоёв)" if n_gpu_layers > 0 else "CPU"
        
        load_start = time.time()
        logger.info(f"🧠 [Qwen3] Загрузка модели (~4.5 GB VRAM, {device_str})...")
        
        def _load_llm():
            return Llama(
                model_path=str(QWEN_MODEL_PATH),
                n_gpu_layers=n_gpu_layers,
                n_ctx=QWEN_N_CTX,
                chat_format="chatml",
                verbose=False,
            )
        
        llm = vram_manager.load_model("llm", _load_llm)
        load_time = time.time() - load_start
        logger.info(f"🧠 [Qwen3] Модель загружена за {load_time:.1f}с")
        
        # Create instructor client
        # instructor.from_llama_cpp() was removed in newer instructor versions.
        # instructor.patch() wraps llama-cpp's OpenAI-v1 API for structured output.
        create_fn = instructor.patch(
            create=llm.create_chat_completion_openai_v1,
            mode=instructor.Mode.JSON_SCHEMA,
        )
        
        # Handle chunked vs single analysis
        if isinstance(context_log_or_chunks, list):
            return self._analyze_chunked(create_fn, context_log_or_chunks, user_instructions, on_progress=on_progress, min_duration=min_duration, max_duration=max_duration, max_moments=max_moments)
        else:
            return self._analyze_single(create_fn, context_log_or_chunks, user_instructions, min_duration=min_duration, max_duration=max_duration, max_moments=max_moments)

    def _analyze_single(
        self,
        create_fn,
        context_log: str,
        user_instructions: str,
        min_duration: int = 60,
        max_duration: int = 90,
        max_moments: int = 15,
    ) -> DirectorOutput:
        """Single-pass LLM analysis for videos that fit in context window."""
        logger.info(f"🧠 [Qwen3] Анализирую контекст ({len(context_log)} символов)...")
        
        analyze_start = time.time()
        
        system_prompt_filled = build_system_prompt(min_duration, max_duration, max_moments, user_instructions)
        
        try:
            result = self._call_with_thinking(create_fn,
                
                model="qwen3",
                response_model=DirectorOutput,
                messages=[
                    {"role": "system", "content": system_prompt_filled + "\n\n/no_think"},
                    {"role": "user", "content": context_log},
                ],
                temperature=QWEN_TEMPERATURE,
                top_p=QWEN_TOP_P,
                presence_penalty=QWEN_PRESENCE_PENALTY,
                max_tokens=3072,  # fits n_ctx 8192 alongside ~4k-token chunk + system prompt
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
        create_fn,
        chunks: list[str],
        user_instructions: str,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        min_duration: int = 60,
        max_duration: int = 90,
        max_moments: int = 15,
    ) -> DirectorOutput:
        """Multi-pass analysis for long videos split into chunks.
        
        Each chunk is analyzed independently, then results are consolidated.
        """
        logger.info(f"🧠 [Qwen3] Режим chunks: анализирую {len(chunks)} частей...")
        
        all_candidates = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"🧠 [Qwen3] Обрабатываю chunk {i+1}/{len(chunks)} ({len(chunk)} символов)...")
            
            chunk_start = time.time()
            system_prompt = build_system_prompt(min_duration, max_duration, max_moments, user_instructions)
            
            try:
                chunk_result = self._call_with_thinking(create_fn,
                
                    model="qwen3",
                    response_model=DirectorOutput,
                    messages=[
                        {"role": "system", "content": system_prompt + "\n\n/no_think"},
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
                
                # Report progress after each chunk
                if on_progress:
                    on_progress(i + 1, len(chunks), "chunk")
                
            except Exception as e:
                logger.error(f"🧠 [Qwen3] Ошибка в chunk {i+1}: {e}")
                continue
        
        # Merge all chunk candidates. Chunks are analyzed independently, so no
        # single pass sees the whole video. We do a lightweight GLOBAL RE-RANK:
        # the LLM picks the best moments ACROSS the entire video by INDEX (it does
        # not regenerate them), so real start/end/virality_score are preserved.
        logger.info(f"🧠 [Qwen3] Объединяю {len(all_candidates)} кандидатов...")
        if on_progress:
            on_progress(len(chunks), len(chunks), "consolidate")

        ranked = all_candidates
        if len(all_candidates) > max_moments:
            try:
                ranked = self._global_rerank(create_fn, all_candidates, max_moments)
                logger.info(f"🧠 [Qwen3] Глобальный ре-ранкинг: {len(all_candidates)} → {len(ranked)} (выбор по всему видео)")
            except Exception as e:
                logger.warning(f"🧠 [Qwen3] Ре-ранкинг не удался ({e}); беру всех кандидатов как есть")
                ranked = all_candidates

        final_result = DirectorOutput(
            moments=ranked,
            total_analyzed=len(all_candidates),
            language_detected="unknown",
        )
        
        vram_manager.unload_model("llm")
        logger.info("🧠 [Qwen3] Модель выгружена из VRAM")
        
        return final_result

    def _global_rerank(self, create_fn, candidates: list, max_moments: int) -> list:
        """Pick the best moments across the WHOLE video by index.

        Chunks are scored in isolation, so a 9/10 in a weak chunk can outrank a
        7/10 in a strong one, and near-duplicates from overlapping chunks survive.
        Here the LLM sees ALL candidates at once and returns the indices of the
        ones to keep, ranked best-first. Crucially it returns INDICES, not new
        moments, so the original objects (real timings + scores) are preserved.
        Returns the reordered/selected subset of `candidates`.
        """
        import json

        lines = ["You are selecting the BEST short-clip moments from an ENTIRE video.",
                 f"There are {len(candidates)} candidates below (from different parts of the video).",
                 "",
                 "Pick the strongest ones, ranked best-first. Rules:",
                 f"- Return AT MOST {max_moments} indices (fewer is better than padding with weak ones).",
                 "- Drop near-duplicates and moments covering the same idea (keep the best one).",
                 "- Prefer moments with a strong self-contained hook that make sense without prior context.",
                 "- Favor variety of content_type.",
                 "",
                 "Respond with ONLY a JSON object: {\"keep\": [list of integer indices, best first]}.",
                 "",
                 "=== CANDIDATES ==="]
        for i, m in enumerate(candidates):
            reason = (getattr(m, "reasoning", "") or "")[:160]
            lines.append(
                f"[{i}] {m.start:.0f}-{m.end:.0f}s | score={getattr(m, 'virality_score', 0):.0f} "
                f"| type={getattr(m, 'content_type', '?')} | hook=\"{getattr(m, 'hook', '')}\" | why={reason}"
            )
        prompt = "\n".join(lines)

        raw = create_fn(
            response_model=None,
            model="qwen3",
            messages=[
                {"role": "system", "content": "You are a viral video editor ranking clip candidates. Respond with JSON only.\n\n/no_think"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        content = raw.choices[0].message.content if (hasattr(raw, "choices") and raw.choices) else str(raw)
        content = _strip_think(content)
        data = json.loads(content)
        keep = data.get("keep", []) if isinstance(data, dict) else data

        seen = set()
        out = []
        for idx in keep:
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(candidates) and idx not in seen:
                seen.add(idx)
                out.append(candidates[idx])
            if len(out) >= max_moments:
                break
        # Log what the global view actually picked (indices + scores) so the
        # re-rank decision is visible, not just the count.
        if out:
            preview = ", ".join(
                f"#{keep[i] if i < len(keep) else '?'}({m.start:.0f}-{m.end:.0f}s,v={getattr(m,'virality_score',0):.0f})"
                for i, m in enumerate(out[:8])
            )
            logger.info(f"🧠 [Qwen3] Ре-ранкинг выбрал {len(out)}: {preview}{' ...' if len(out) > 8 else ''}")
        else:
            logger.warning("🧠 [Qwen3] Ре-ранкинг не вернул валидных индексов — беру всех кандидатов")
        # Safety: if the model returned nothing usable, fall back to all candidates.
        return out if out else candidates

    def _consolidate_moments(self, create_fn, candidates: list) -> DirectorOutput:
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
        
        result = self._call_with_thinking(create_fn,
                
            model="qwen3",
            response_model=DirectorOutput,
            messages=[
                {"role": "system", "content": "You are a viral video editor consolidating moment candidates.\n\n/no_think"},
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