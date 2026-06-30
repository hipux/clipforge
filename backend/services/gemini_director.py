"""Gemini LLM Director — cloud primary, with proxy support for region blocks.

Same `analyze(...)` contract as `llm_director.py` (Qwen3-8B local). The
detection pipeline tries Gemini first; on any failure it falls back to Qwen.

Why a separate cloud model at all:
  * Prompt adherence — Gemini differentiates virality_score / hook_strength /
    self_contained, where Qwen3-8B returns flat scores and forces the
    deterministic rescoring in detection_pipeline to compensate.
  * Multimodal — Gemini can take image parts (planned: host-reaction frames),
    which text-only Qwen cannot. This is the honest fix for "the model rated
    the embedded video's hook as the moment".

Region note: the Gemini API geoblocks by caller IP and Russia is unsupported.
All requests MUST egress through a proxy in a supported region. A datacenter
proxy/VPS works — the API keys on IP, not on residential status.
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional, Callable

import httpx

from backend.gpu_config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_PROXY,
    GEMINI_TIMEOUT, GEMINI_MAX_RETRIES, GEMINI_RETRY_BASE_DELAY,
    GEMINI_HEALTH_TTL,
    _GEMINI_TRANSIENT_STATUS_CODES,
)
from backend.services.context_builder import build_system_prompt
from backend.services.content_presets import apply_to_prompt, get_preset
from backend.schemas.moment_instruction import DirectorOutput

logger = logging.getLogger(__name__)

# Gemini generates a lot of reasoning before JSON; allow a generous budget.
_MAX_OUTPUT_TOKENS = 8192
_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class _TransientGeminiError(RuntimeError):
    """A Gemini API error that warrants a retry (503/429/timeout-class).

    Distinguishing transient from terminal errors is important: re-trying a
    403 region-block just wastes time before falling back to Qwen. Steady
    503/429 means Google's side is overloaded and the issue will pass.
    """


def _is_transient_response(status_code: int) -> bool:
    """True iff the status indicates a transient infrastructure problem.

    429 = quota/rate limit (often transient; the key can briefly exceed TPM).
    5xx = Google's service is degraded / overloaded.
    """
    return status_code in _GEMINI_TRANSIENT_STATUS_CODES


def _after_attempt_delay(attempt: int) -> float:
    """Exponential backoff between retries: base * 2^(attempt-1).

    attempt=1 → no extra wait (we just tried once)
    attempt=2 → GEMINI_RETRY_BASE_DELAY (default 5s)
    attempt=3 → base * 2            (default 10s)
    attempt=4 → base * 4            (default 20s)
    """
    if attempt <= 1:
        return 0.0
    return GEMINI_RETRY_BASE_DELAY * (2 ** (attempt - 2))


class GeminiNotConfiguredError(RuntimeError):
    """Raised when Gemini is requested but not configured (no key/proxy)."""


def _build_client() -> httpx.Client:
    """httpx client routed through the configured proxy."""
    if not GEMINI_PROXY:
        raise GeminiNotConfiguredError(
            "GEMINI_PROXY is not set. Gemini API is region-blocked from Russia; "
            "set CLIPFORGE_GEMINI_PROXY to a proxy in a supported region, or use Qwen."
        )
    # httpx accepts a single proxy URL for all schemes here.
    return httpx.Client(
        proxy=GEMINI_PROXY,
        timeout=httpx.Timeout(GEMINI_TIMEOUT, connect=30.0),
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
    )


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a model response that may have preamble.

    Gemini usually returns clean JSON, but thinking-mode can wrap it in prose
    or markdown fences. We isolate the outermost {...} block.
    """
    text = text.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = text.split("```", 2)
        # take the middle section (between first and last fence)
        if len(text) >= 2:
            # remove optional language tag on the first fence line
            text = text[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            # cut off a trailing fence if it got bundled in
            if text.endswith("```"):
                text = text[:-3].strip()
    # Find the outermost balanced braces.
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text  # best effort


def _generate_with_retry(
    client: httpx.Client,
    system_prompt: str,
    user_content: str,
    temperature: float,
    operation: str = "generate",
) -> str:
    """Call generateContent with retry-on-transient and exponential backoff.

    Returns the model's text output. Raises:
      * RuntimeError with the LAST error message after exhausting retries on a
        transient error (caller can fall back to Qwen);
      * RuntimeError IMMEDIATELY on a terminal error (400/403/404) — those are
        configuration problems re-trying won't fix.
    """
    url = f"{_API_BASE}/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": temperature,
            "topP": 0.95,
            "maxOutputTokens": _MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
        },
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 2):  # 1..MAX_RETRIES+1 attempts
        try:
            resp = client.post(url, json=payload)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            # Transport-level timeout — same retry policy as 5xx. Network blips
            # happen with proxies/datacenter hops and are usually transient.
            last_error = e
            logger.warning(
                f"🛰️  [Gemini] {operation} попытка {attempt}/{GEMINI_MAX_RETRIES+1} — "
                f"сетевая ошибка ({type(e).__name__}: {e})"
            )
            delay = _after_attempt_delay(attempt)
            if delay:
                time.sleep(delay)
            continue

        if resp.status_code == 200:
            data = resp.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts)
            except (KeyError, IndexError):
                # finishReason could be SAFETY/RECITATION — treat as transient
                # because Google's safety block flips on/off without warning.
                finish = data.get("candidates", [{}])[0].get("finishReason", "UNKNOWN")
                last_error = RuntimeError(f"Gemini returned no content (finishReason={finish})")
                logger.warning(
                    f"🛰️  [Gemini] {operation} попытка {attempt}/{GEMINI_MAX_RETRIES+1} — "
                    f"пустой ответ (finishReason={finish})"
                )
                delay = _after_attempt_delay(attempt)
                if delay:
                    time.sleep(delay)
                continue

        body = resp.text[:500]
        if _is_transient_response(resp.status_code):
            last_error = RuntimeError(f"Gemini API {resp.status_code}: {body}")
            # Lesson from the 503 incident: a single transient overload was
            # enough to fall back to Qwen for the WHOLE video (~830s for a
            # 31-min render). Instead, wait it out — overloads rarely last
            # more than ~30 seconds.
            logger.warning(
                f"🛰️  [Gemini] {operation} попытка {attempt}/{GEMINI_MAX_RETRIES+1} — "
                f"transient {resp.status_code} (повтор через "
                f"{_after_attempt_delay(attempt):.0f}с)"
            )
            delay = _after_attempt_delay(attempt)
            if delay:
                time.sleep(delay)
            continue

        # Terminal error: 400/403 (region block / bad key) / 404 / etc.
        # Retrying won't help — surface immediately so the pipeline can fall
        # back to Qwen without burning seconds on an unfixable call.
        raise RuntimeError(f"Gemini API {resp.status_code}: {body}")

    # Exhausted retries on a transient problem — propagate the last error
    # so the caller can fall back to Qwen. We do NOT silently return "" —
    # falling back vs empty-output confusion MUST be visible.
    raise last_error  # type: ignore[misc]


def _generate(client: httpx.Client, system_prompt: str, user_content: str, temperature: float) -> str:
    """Back-compat wrapper. Prefer `_generate_with_retry(... operation="...")`.

    Kept as a thin alias — older code paths may still import this name.
    """
    return _generate_with_retry(client, system_prompt, user_content, temperature, operation="generate")


class GeminiDirector:
    """Cloud Gemini director, same contract as LLMDirector.analyze()."""

    # Class-level so the cache survives across director instances if anyone
    # ever recreates one (also matches the singleton pattern used for the
    # instance below). `_last_ok_monotonic` is set on success and consulted
    # by `check_health` to skip the RPD-1 pre-flight on a fresh session.
    _health_cache = {
        "ok_at_monotonic": None,   # float | None — last successful check
        "ttl_sec":          GEMINI_HEALTH_TTL,  # 0 disables caching
    }

    def check_health(self, *, force: bool = False) -> bool:
        """Cheap pre-flight: is the proxy reachable and the API key valid?

        Sends a tiny request (1 input token, 1 output token) so we can decide
        BEFORE chunking the video whether to build a single big context (Gemini
        can hold 1M tokens) or fall back to Qwen (which needs small chunks).

        **RPD-friendly.** On the Gemini 3.5 Flash free tier (≈20 RPD), the
        pre-flight is itself a billable call — re-running it for every
        detection halves the daily video budget. We memoize a successful
        result for `GEMINI_HEALTH_TTL` seconds (default 5 min, configurable).
        A terminal failure during `analyze()` invalidates the cache so the
        next detection re-checks (cheap, but accurate).

        Pass `force=True` to bypass the cache (e.g. on operator demand).

        Retries TRANSIENT errors (503/429/timeout) up to GEMINI_MAX_RETRIES
        times with exponential backoff.
        """
        if not (GEMINI_API_KEY and GEMINI_PROXY):
            return False
        # Cached success within TTL? Skip the pre-flight entirely.
        ttl = self._health_cache.get("ttl_sec", GEMINI_HEALTH_TTL) or 0
        cached_at = self._health_cache.get("ok_at_monotonic")
        if not force and ttl > 0 and cached_at is not None \
                and (time.monotonic() - cached_at) < ttl:
            age = time.monotonic() - cached_at
            logger.info(
                f"🛰️  [Gemini] Пре-полёт пропущен (cached, {age:.0f}с назад, TTL {ttl:.0f}с) — "
                f"экономит 1 RPD"
            )
            return True

        # The SOCKS-proxy-via-httpx failure mode is a classic ImportError raised
        # deep inside httpx when socksio is not installed. Detect it up-front
        # so the log points the user at the actual fix (pip install socksio)
        # instead of an opaque "HTTPConnectionError" later.
        if GEMINI_PROXY.lower().startswith(("socks5://", "socks4://")):
            try:
                import socksio  # noqa: F401
            except ImportError:
                logger.warning(
                    "🛰️  [Gemini] Проверка доступности провалена: socksio не установлен. "
                    "Для SOCKS-прокси требуется: pip install socksio"
                )
                return False

        url = f"{_API_BASE}/models/{GEMINI_MODEL}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with: OK"}]}],
            "generationConfig": {"maxOutputTokens": 16, "temperature": 0},
        }
        for attempt in range(1, GEMINI_MAX_RETRIES + 2):
            try:
                with _build_client() as client:
                    resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("🛰️  [Gemini] Проверка доступности: OK (прокси+ключ работают)")
                    self._health_cache["ok_at_monotonic"] = time.monotonic()
                    return True
                if _is_transient_response(resp.status_code):
                    logger.warning(
                        f"🛰️  [Gemini] Пре-полёт: transient {resp.status_code} "
                        f"(попытка {attempt}/{GEMINI_MAX_RETRIES+1})"
                    )
                    body = resp.text[:200]
                    logger.debug(f"🛰️  [Gemini] Тело ответа при {resp.status_code}: {body}")
                    delay = _after_attempt_delay(attempt)
                    if delay:
                        time.sleep(delay)
                    continue
                logger.warning(
                    f"🛰️  [Gemini] Проверка доступности провалена (terminal): "
                    f"{resp.status_code} {resp.text[:200]}"
                )
                self._health_cache["ok_at_monotonic"] = None
                return False
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning(
                    f"🛰️  [Gemini] Пре-полёт: сетевая ошибка "
                    f"({type(e).__name__}: {e}) — попытка {attempt}/{GEMINI_MAX_RETRIES+1}"
                )
                delay = _after_attempt_delay(attempt)
                if delay:
                    time.sleep(delay)
                continue
            except Exception as e:
                logger.warning(f"🛰️  [Gemini] Проверка доступности провалена: {type(e).__name__}: {e}")
                self._health_cache["ok_at_monotonic"] = None
                return False

        # Exhausted retries — invalidate any stale cache so the next call
        # re-evaluates rather than trusting a pre-flight from minutes ago.
        self._health_cache["ok_at_monotonic"] = None
        logger.warning(
            f"🛰️  [Gemini] Пре-полётный check исчерпал {GEMINI_MAX_RETRIES+1} попыток "
            f"— переключаюсь на локальный Qwen3-8B"
        )
        return False

    def invalidate_health_cache(self) -> None:
        """Force the next check_health() to actually hit the API.

        `analyze()` calls this on terminal (non-transient) failures so the
        next detection retries the probe instead of trusting a stale "OK".
        """
        self._health_cache["ok_at_monotonic"] = None

    def analyze(
        self,
        context_log_or_chunks: str | list[str],
        user_instructions: str = "",
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        min_duration: int = 60,
        max_duration: int = 90,
        max_moments: int = 15,
        preset_id: str = "default",
    ) -> DirectorOutput:
        if not (GEMINI_API_KEY and GEMINI_PROXY):
            raise GeminiNotConfiguredError("Gemini needs both API key and proxy.")

        # Build the shared system prompt once — apply content preset (#4)
        # rules inside the LLM system prompt via pure-string insertion.
        system_prompt = apply_to_prompt(
            build_system_prompt(min_duration, max_duration, max_moments, user_instructions),
            get_preset(preset_id),
        )

        if isinstance(context_log_or_chunks, list):
            return self._analyze_chunked(system_prompt, context_log_or_chunks, on_progress, max_moments)
        return self._analyze_single(system_prompt, context_log_or_chunks)

    def _call(self, client: httpx.Client, system_prompt: str, content: str) -> DirectorOutput:
        """One generateContent call → validated DirectorOutput with ONE retry
        on validation failure.

        Retries on transient transport errors (503/429/timeout) happen INSIDE
        _generate_with_retry. We add ONE additional attempt here for the
        very common failure mode of "Gemini emitted JSON but truncated it
        mid-array because the output-token budget ran out" — the production
        log shows a 47k-character single-context input where the model
        started a huge `moments` array, used up 8k output tokens on
        reasoning + first 3 moments, then was cut off at `},\n    },`. A
        second attempt usually fits (output is non-deterministic).

        After ONE retry, we let the validation error propagate so the
        pipeline can fall back to Qwen — beyond that, retries don't pay
        off (the model is stuck).
        """
        from pydantic import ValidationError

        last_error: Optional[Exception] = None
        last_text: str = ""
        for attempt in range(1, 3):  # 1 = initial, 2 = exactly one retry
            try:
                text = _generate(client, system_prompt, content, temperature=0.3)
                # _generate_with_retry re-raises non-transient status codes
                # (`res.raise_for_status()`), so any raise from here is something
                # the client BRICKED on (terminal). Invalidate the health
                # cache so the next detection re-probes instead of trusting
                # a fake "OK" from minutes ago.
                clean = _extract_json(text)
                last_text = clean  # keep for failure-log below
                return DirectorOutput.model_validate_json(clean)
            except ValidationError as e:
                last_error = e
                # Snapshot WHY validation failed — the first line of the
                # pydantic error distinguishes "JSON truncated" vs
                # "field N missing", which is critical for diagnosing
                # future regressions vs prompt issues.
                logger.warning(
                    f"🛰️  [Gemini] Попытка {attempt}: ответ не прошёл "
                    f"валидацию ({type(e).__name__}: "
                    f"{str(e).splitlines()[0][:200]}). Повтор..."
                )
                logger.debug(
                    f"🛰️  [Gemini] Текст, который не прошёл валидацию "
                    f"(первые 400 символов): {last_text[:400]!r}"
                )
                # Short pause — avoid hammering a tired server in lockstep
                # with our own retry storm.
                time.sleep(2.0)
            except (httpx.HTTPStatusError, httpx.TimeoutException,
                    httpx.ConnectError, httpx.NetworkError) as e:
                self.invalidate_health_cache()
                raise
        # Both attempts produced invalid JSON — propagate so the pipeline
        # can fall back to Qwen with the exception intact.
        raise last_error  # type: ignore[misc]  pydantic.ValidationError

    def _analyze_single(self, system_prompt: str, context_log: str) -> DirectorOutput:
        logger.info(f"🛰️  [Gemini] Анализирую контекст ({len(context_log)} символов)...")
        # _generate_with_retry already handles transient retries — but we
        # add one more outer pass to swallow the WHOLE retry budget on a
        # single-context call (since there's nothing to skip).
        with _build_client() as client:
            return self._call(client, system_prompt, context_log)

    def _analyze_chunked(
        self,
        system_prompt: str,
        chunks: list[str],
        on_progress: Optional[Callable[[int, int, str], None]],
        max_moments: int,
    ) -> DirectorOutput:
        logger.info(f"🛰️  [Gemini] Режим chunks: анализирую {len(chunks)} частей...")
        all_candidates: list = []
        first_chunk_error: Optional[Exception] = None

        # Reuse ONE client (and its proxy connection) across all chunk calls.
        # Each _call already retry-with-backoff handles transient errors, so
        # this loop is the "outer" pass that decides what to do if even
        # that fails: skip the chunk (later ones) or fail-fast (first one).
        with _build_client() as client:
            for i, chunk in enumerate(chunks):
                chunk_start = time.time()
                try:
                    result = self._call(client, system_prompt, chunk)
                except Exception as e:
                    logger.error(
                        f"🛰️  [Gemini] Chunk {i+1}/{len(chunks)} провалился "
                        f"после {GEMINI_MAX_RETRIES+1} попыток: {e}"
                    )
                    if i == 0:
                        # If the very first chunk can't be served, the
                        # region/quota situation is unlikely to recover for
                        # the rest — fail fast so the pipeline can fall back.
                        first_chunk_error = e
                        break
                    # Mid-batch failure: continue with what we have. We'd
                    # rather have partial results than throw the whole run.
                    continue
                elapsed = time.time() - chunk_start
                logger.info(
                    f"🛰️  [Gemini] Chunk {i+1}/{len(chunks)} за {elapsed:.1f}с: "
                    f"{len(result.moments)} моментов"
                )
                all_candidates.extend(result.moments)
                if on_progress:
                    on_progress(i + 1, len(chunks), "chunk")

        if not all_candidates:
            # No chunks produced any output — propagate the (last) error so
            # the caller can fall back to Qwen.
            if first_chunk_error is not None:
                raise first_chunk_error
            raise RuntimeError("Gemini produced no candidates")

        if len(all_candidates) > max_moments:
            logger.info(f"🛰️  [Gemini] Объединяю {len(all_candidates)} кандидатов...")
            if on_progress:
                on_progress(len(chunks), len(chunks), "consolidate")
            # Reuse the client for the consolidation call. Keep best max_moments.
            all_candidates.sort(
                key=lambda m: float(getattr(m, "virality_score", 0) or 0), reverse=True
            )
            # Dedup near-overlaps (same rule as the pipeline's overlap filter).
            kept: list = []
            for m in all_candidates:
                overlap = any(
                    (min(m.end, k.end) - max(m.start, k.start)) > 0
                    and (min(m.end, k.end) - max(m.start, k.start)) >
                    0.5 * min(m.end - m.start, k.end - k.start)
                    for k in kept
                )
                if not overlap:
                    kept.append(m)
                if len(kept) >= max_moments:
                    break
            all_candidates = kept

        kept.sort(key=lambda m: float(getattr(m, "start", 0)))  # chronological for display
        return DirectorOutput(
            moments=all_candidates,
            total_analyzed=len(all_candidates),
            language_detected="unknown",
        )


# Global singleton instance
gemini_director = GeminiDirector()
