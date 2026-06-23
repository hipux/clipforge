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

# Try to import huggingface_hub for robust model downloads (handles auth, resumable, case-sensitive filenames)
try:
    from huggingface_hub import hf_hub_download as _hf_hub_download
    _HF_HUB_AVAILABLE = True
except ImportError:
    _HF_HUB_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMDirector:
    """Qwen3-8B Q4_K_M GGUF via llama-cpp-python.
    
    GPU-first: n_gpu_layers=-1 loads all layers on GPU.
    Uses instructor library for structured JSON output.
    """

    def _download_model_if_needed(self) -> None:
        """Download Qwen3-8B GGUF with resumable Range-request download.
        
        Uses HTTP Range headers + retry loop to handle HuggingFace CDN drops.
        Never deletes a partial file — always resumes from where it left off.
        """
        import time as _time

        EXPECTED_SIZE = 5_030_000_000  # ~4.7 GB — abort if server reports different (sanity check)
        MIN_VALID_SIZE = 4_500_000_000  # accept if >= 4.5 GB (allows slight variation)

        # Check if model already fully downloaded
        if QWEN_MODEL_PATH.exists():
            size = QWEN_MODEL_PATH.stat().st_size
            if size >= MIN_VALID_SIZE:
                logger.info(f"🧠 [Qwen3] Модель найдена: {QWEN_MODEL_PATH} ({size/1e9:.2f} GB)")
                return
            else:
                logger.info(f"🧠 [Qwen3] Частично скачана: {size/1e6:.0f} MB — возобновляю...")

        logger.info(f"🧠 [Qwen3] Скачиваю модель (~4.7 GB), подождите...")
        logger.info("🧠 [Qwen3] Resumable download: автоматически продолжается при обрывах соединения")

        QWEN_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

        url = f"https://huggingface.co/{QWEN_MODEL_REPO}/resolve/main/{QWEN_MODEL_FILE}"
        tmp_path = QWEN_MODEL_PATH.with_suffix('.part')

        # Get total file size from HEAD
        try:
            head = requests.head(url, allow_redirects=True, timeout=30)
            total_size = int(head.headers.get('content-length', 0))
            if total_size < MIN_VALID_SIZE:
                # HEAD may not return content-length on redirect — try GET
                total_size = 0
        except Exception:
            total_size = 0

        MAX_RETRIES = 50        # unlimited practical retries
        RETRY_DELAY = 5         # seconds between retries
        CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunks
        READ_TIMEOUT = 60       # seconds per chunk read
        CONNECT_TIMEOUT = 30    # seconds to establish connection

        attempt = 0
        last_log_pct = -1

        while attempt < MAX_RETRIES:
            attempt += 1

            # Calculate resume offset
            resume_from = tmp_path.stat().st_size if tmp_path.exists() else 0
            # Also check if final path has partial content
            if resume_from == 0 and QWEN_MODEL_PATH.exists():
                resume_from = QWEN_MODEL_PATH.stat().st_size
                if resume_from >= MIN_VALID_SIZE:
                    break  # done
                # rename to .part to resume
                import shutil
                shutil.move(str(QWEN_MODEL_PATH), str(tmp_path))

            headers = {}
            if resume_from > 0:
                headers['Range'] = f'bytes={resume_from}-'
                logger.info(f"🧠 [Qwen3] Попытка {attempt}: возобновляю с {resume_from/1e6:.0f} MB...")
            else:
                logger.info(f"🧠 [Qwen3] Попытка {attempt}: начинаю скачивание...")

            try:
                with requests.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    allow_redirects=True
                ) as r:
                    if r.status_code == 416:  # Range Not Satisfiable = already complete
                        logger.info("🧠 [Qwen3] Файл уже полностью скачан (416 Range Not Satisfiable)")
                        break
                    r.raise_for_status()

                    # Get total size from response if not known
                    if total_size == 0:
                        cr = r.headers.get('content-range', '')
                        if cr:  # e.g. "bytes 16777216-5029999999/5030000000"
                            try:
                                total_size = int(cr.split('/')[-1])
                            except Exception:
                                pass
                        if total_size == 0:
                            total_size = int(r.headers.get('content-length', 0)) + resume_from

                    write_mode = 'ab' if resume_from > 0 else 'wb'
                    with open(tmp_path, write_mode) as f:
                        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                            if chunk:
                                f.write(chunk)
                                current_size = resume_from + f.tell() if resume_from else f.tell()

                                # Log progress every 5%
                                if total_size > 0:
                                    pct = current_size / total_size * 100
                                    pct_bucket = int(pct / 5) * 5
                                    if pct_bucket > last_log_pct:
                                        last_log_pct = pct_bucket
                                        logger.info(
                                            f"🧠 [Qwen3] Скачано: {pct:.0f}% "
                                            f"({current_size/1e9:.2f}/{total_size/1e9:.2f} GB)"
                                        )

                # Check if download complete
                downloaded_size = tmp_path.stat().st_size if tmp_path.exists() else 0
                if downloaded_size >= MIN_VALID_SIZE:
                    import shutil
                    shutil.move(str(tmp_path), str(QWEN_MODEL_PATH))
                    logger.info(f"🧠 [Qwen3] ✓ Модель скачана: {downloaded_size/1e9:.2f} GB")
                    return
                else:
                    logger.warning(
                        f"🧠 [Qwen3] Неполная загрузка: {downloaded_size/1e6:.0f} MB. "
                        f"Повтор через {RETRY_DELAY}с..."
                    )
                    _time.sleep(RETRY_DELAY)

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout) as e:
                downloaded_size = tmp_path.stat().st_size if tmp_path.exists() else 0
                logger.warning(
                    f"🧠 [Qwen3] Обрыв соединения ({type(e).__name__}): "
                    f"{downloaded_size/1e6:.0f} MB сохранено. "
                    f"Повтор {attempt}/{MAX_RETRIES} через {RETRY_DELAY}с..."
                )
                _time.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"🧠 [Qwen3] Ошибка загрузки: {e}")
                raise RuntimeError(f"Failed to download Qwen model: {e}")

        # Final check
        final_size = QWEN_MODEL_PATH.stat().st_size if QWEN_MODEL_PATH.exists() else 0
        if final_size < MIN_VALID_SIZE:
            raise RuntimeError(
                f"Failed to download Qwen model after {MAX_RETRIES} attempts. "
                f"Downloaded: {final_size/1e6:.0f} MB / {MIN_VALID_SIZE/1e9:.1f} GB required"
            )

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
            return self._analyze_chunked(create_fn, context_log_or_chunks, user_instructions)
        else:
            return self._analyze_single(create_fn, context_log_or_chunks, user_instructions)

    def _analyze_single(
        self,
        create_fn,
        context_log: str,
        user_instructions: str
    ) -> DirectorOutput:
        """Single-pass LLM analysis for videos that fit in context window."""
        logger.info(f"🧠 [Qwen3] Анализирую контекст ({len(context_log)} символов)...")
        
        analyze_start = time.time()
        
        system_prompt_filled = SYSTEM_PROMPT.format(user_instructions=user_instructions or "Нет")
        
        try:
            result = create_fn(
                model="qwen3",
                response_model=DirectorOutput,
                messages=[
                    {"role": "system", "content": system_prompt_filled + "\n/no_think"},
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
        create_fn,
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
                chunk_result = create_fn(
                    model="qwen3",
                    response_model=DirectorOutput,
                    messages=[
                        {"role": "system", "content": system_prompt + "\n/no_think"},
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
        final_result = self._consolidate_moments(create_fn, all_candidates)
        
        vram_manager.unload_model("llm")
        logger.info("🧠 [Qwen3] Модель выгружена из VRAM")
        
        return final_result

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
        
        result = create_fn(
            model="qwen3",
            response_model=DirectorOutput,
            messages=[
                {"role": "system", "content": "You are a viral video editor consolidating moment candidates.\n/no_think"},
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
