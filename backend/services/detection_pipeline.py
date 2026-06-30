"""GPU detection pipeline orchestrator - coordinates 3-stage analysis.

Stage 1: Data Collection (Whisper + YOLO + Librosa)
Stage 2: LLM Director (Qwen2.5-7B)
Stage 3: Rendering (handled separately via API)
"""
from __future__ import annotations
import logging
import os
import asyncio
import subprocess
from typing import AsyncGenerator, Optional, Callable
from backend.services.vram_manager import vram_manager
from backend.services.whisper_gpu import whisper_gpu
from backend.services.face_detector import face_detector
from backend.services.audio_analyzer import audio_analyzer
from backend.services.context_builder import context_builder
from backend.services.llm_director import llm_director
from backend.services.gemini_director import gemini_director
from backend.gpu_config import gemini_is_configured, GEMINI_MODEL
from backend.schemas.moment_instruction import Stage1Context, DirectorOutput

logger = logging.getLogger(__name__)


def _ffmpeg_to_wav(video_path: str, out_wav_path: str) -> None:
    """Extract mono 16 kHz PCM float from `video_path` to `out_wav_path`.

    Uses ffmpeg via subprocess — same tool Whisper already uses for audio.
    Pulled into a single helper because we only need the raw audio for
    pyannote-audio diarization; we don't need transcripts or timestamps
    from this pass.
    """
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-i", video_path,
        "-ac", "1",            # mono
        "-ar", "16000",        # 16 kHz (pyannote.audio 4.x requirement)
        "-sample_fmt", "s16le",
        "-f", "wav",
        out_wav_path,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"_ffmpeg_to_wav failed: rc={r.returncode}, stderr={r.stderr.decode(errors='replace')[:300]}"
        )


def _signal_for_window(ctx, start, end):
    """Return (avg_rms, peak_energy, speech_chars) for a time window from Stage 1 data.
    Defensive against both object- and dict-shaped entries."""
    if ctx is None:
        return (0.0, 0.0, 0.0, 0.0)
    aa = getattr(ctx, "audio_analysis", None)
    avg_rms = peak_energy = 0.0
    if aa is not None:
        rms_list = getattr(aa, "rms_timeline", None) or []
        vals = []
        for r in rms_list:
            t = r.get("time") if isinstance(r, dict) else getattr(r, "time", None)
            v = r.get("rms") if isinstance(r, dict) else getattr(r, "rms", None)
            if t is not None and v is not None and start <= float(t) <= end:
                vals.append(float(v))
        avg_rms = sum(vals) / len(vals) if vals else 0.0
        for p in (getattr(aa, "peaks", None) or []):
            t = p.get("timestamp") if isinstance(p, dict) else getattr(p, "timestamp", None)
            mag = p.get("magnitude") if isinstance(p, dict) else getattr(p, "magnitude", 0.0)
            if t is not None and start <= float(t) <= end:
                peak_energy += float(mag or 0.0)
    # YamNet semantic events (laughter/applause/cheering) inside the window —
    # a strong, content-aware virality signal beyond raw energy.
    event_energy = 0.0
    if aa is not None:
        for ev in (getattr(aa, "events", None) or []):
            t = ev.get("timestamp") if isinstance(ev, dict) else getattr(ev, "timestamp", None)
            sc = ev.get("score") if isinstance(ev, dict) else getattr(ev, "score", 0.0)
            if t is not None and start <= float(t) <= end:
                event_energy += float(sc or 0.0)
    chars = 0
    for seg in (getattr(ctx, "transcript", None) or []):
        s = seg.get("start") if isinstance(seg, dict) else getattr(seg, "start", None)
        e = seg.get("end") if isinstance(seg, dict) else getattr(seg, "end", None)
        txt = seg.get("text") if isinstance(seg, dict) else getattr(seg, "text", "")
        if s is not None and e is not None and float(e) >= start and float(s) <= end:
            chars += len(txt or "")
    return (avg_rms, peak_energy, float(chars), event_energy)


def _sentences(ctx):
    """Flat, time-sorted list of transcript sentences: {start, end}."""
    out = []
    for seg in (getattr(ctx, "transcript", None) or []):
        s = seg.get("start") if isinstance(seg, dict) else getattr(seg, "start", None)
        e = seg.get("end") if isinstance(seg, dict) else getattr(seg, "end", None)
        if s is None or e is None:
            continue
        out.append({"start": float(s), "end": float(e)})
    out.sort(key=lambda x: x["start"])
    return out


def _refine_start(sentences, start, lookback=6.0, pause_threshold=0.45):
    """Move the clip start to a clean, context-giving boundary. Content-agnostic.

    Works for ANY video (no domain keywords). Two universal rules:
      1) never start mid-sentence -> snap back to the start of the sentence the
         chosen start falls into;
      2) prefer the natural start of the current spoken segment: within `lookback`
         seconds, pick the earliest sentence that begins right after a noticeable
         pause (silence gap >= pause_threshold). A pause almost always marks the
         beginning of a new thought, so the clip opens with context/the hook.
    """
    if not sentences:
        return max(0.0, start)
    # sentence containing (or just before) the chosen start
    containing = None
    idx = 0
    for i, sen in enumerate(sentences):
        if sen["start"] <= start + 0.5:
            containing = sen
            idx = i
        else:
            break
    snapped = containing["start"] if containing else max(0.0, start)
    # walk back through the lookback window; remember the earliest sentence that
    # follows a real pause -> that's where the current segment naturally began.
    best = snapped
    j = idx
    while j >= 0 and sentences[j]["start"] >= snapped - lookback:
        prev_end = sentences[j - 1]["end"] if j > 0 else 0.0
        gap = sentences[j]["start"] - prev_end
        if gap >= pause_threshold:
            best = sentences[j]["start"]
        j -= 1
    return max(0.0, best)


def _global_stats(ctx, video_duration):
    """Absolute statistics over the WHOLE video (not just candidates).

    Absolute scoring needs a global baseline so a weak clip in a weak video
    does not score 100 just by being the loudest among the candidates.
    Aggregates the whole-timeline signals Stage 1 already produced:
      rms values, peak magnitudes, speech density (chars/sec), event scores.
    Returns a stats dict, or None if there is no audio analysis.
    """
    if ctx is None or video_duration <= 0:
        return None
    aa = getattr(ctx, "audio_analysis", None)
    if aa is None:
        return None
    rms_vals, peak_vals, ev_vals = [], [], []
    for r in (getattr(aa, "rms_timeline", None) or []):
        v = r.get("rms") if isinstance(r, dict) else getattr(r, "rms", None)
        if v is not None:
            rms_vals.append(float(v))
    for p in (getattr(aa, "peaks", None) or []):
        mag = p.get("magnitude") if isinstance(p, dict) else getattr(p, "magnitude", 0.0)
        peak_vals.append(float(mag or 0.0))
    for ev in (getattr(aa, "events", None) or []):
        sc = ev.get("score") if isinstance(ev, dict) else getattr(ev, "score", 0.0)
        ev_vals.append(float(sc or 0.0))
    # speech density: total chars / total duration
    total_chars = 0.0
    for seg in (getattr(ctx, "transcript", None) or []):
        txt = seg.get("text") if isinstance(seg, dict) else getattr(seg, "text", "")
        total_chars += len(txt or "")
    speech_rate = total_chars / max(video_duration, 1.0)  # chars/sec global
    import statistics
    def _safe(vals, fn):
        return fn(vals) if vals else 0.0
    return {
        "rms_mean": _safe(rms_vals, statistics.mean),
        "rms_p85": _safe(sorted(rms_vals), lambda v: v[int(len(v) * 0.85)] if v else 0.0),
        "peak_p85": _safe(sorted(peak_vals), lambda v: v[int(len(v) * 0.85)] if v else 0.0),
        "speech_rate": speech_rate,
        "event_total": sum(ev_vals),
        "has_events": len(ev_vals) > 0,
    }


def _abs_components(sig, gstats):
    """Map a window's raw signals to 0..1 using ABSOLUTE global thresholds.

    Unlike min-max over candidates, this is bounded by the whole video: a
    window only scores high if it is genuinely strong relative to the entire
    timeline, not merely the strongest of a weak bunch.
    """
    avg_rms, peak_energy, chars, event_energy = sig
    # energy: above the 85th percentile of the whole video is "strong" (->1)
    rms_thr = max(gstats["rms_p85"], gstats["rms_mean"] * 1.4, 1e-6)
    peak_thr = max(gstats["peak_p85"], 1e-6)
    e_rms = min(1.0, avg_rms / rms_thr)
    e_peak = min(1.0, peak_energy / peak_thr) if peak_thr > 1e-9 else 0.0
    # speech density: relative to the global chars/sec rate
    s_thr = max(gstats["speech_rate"], 1.0)
    e_speech = min(1.0, chars / (s_thr * 30.0))  # ~30s window baseline
    # semantic events: absolute (sum of YamNet scores in window)
    e_event = min(1.0, event_energy / 1.5)
    return e_rms, e_peak, e_speech, e_event


def _enforce_constraints(moments, min_duration, max_duration, max_moments, video_duration, ctx=None):
    """Deterministically enforce the user's Detection Settings on LLM output.

    The local LLM frequently ignores the prompt rules: it returns clips that are
    far too short (4-24s), pads the list, and omits virality_score (so every clip
    collapses to the schema default of 50). We fix all of that here:
      * size each clip to a target length that scales with its signal strength,
        so durations vary naturally between min_duration and max_duration;
      * trim clips longer than max_duration, drop ones too short to be usable;
      * compute a REAL virality_score from audio energy + speech density when the
        model failed to differentiate (all scores identical);
      * remove heavy overlaps, sort by score, cap to max_moments, then restore
        chronological order for display.
    """
    # 1) Sample signals per moment (widen short windows so density is comparable).
    raw = []
    for mo in moments:
        start = max(0.0, float(mo.start))
        end = float(mo.end)
        if end <= start:
            raw.append(None)
            continue
        we = max(end, min(start + min_duration, video_duration))
        raw.append(_signal_for_window(ctx, start, we))

    # ── ABSOLUTE SCORING ─────────────────────────────────────────────────────
    # Old code normalized min-max OVER THE CANDIDATES, which meant the loudest
    # candidate always scored ~95 even in a totally weak video. Now we compare
    # each window against the WHOLE VIDEO's statistics, so a weak clip can only
    # score high if it is genuinely strong relative to the entire timeline.
    gstats = _global_stats(ctx, video_duration)

    sentences = _sentences(ctx)

    model_scores = [float(getattr(m, "virality_score", 0) or 0) for m in moments]
    model_has_variance = (max(model_scores) - min(model_scores) > 1.0) if model_scores else False

    # Diagnostics: how the new features see the input.
    n_events_total = len(getattr(getattr(ctx, "audio_analysis", None), "events", None) or [])
    model_hooks_in = [float(getattr(m, "hook_strength", 0.0) or 0.0) for m in moments]
    n_model_hooks = sum(1 for h in model_hooks_in if h > 0.0)
    model_sc_in = [float(getattr(m, "self_contained", 0.5) or 0.5) for m in moments]
    logger.info(
        f"⚙️  [Ограничения] Вход: {len(moments)} кандидатов | "
        f"score модели {'РАЗНЫЙ' if model_has_variance else 'плоский→пересчёт'} "
        f"(min={min(model_scores) if model_scores else 0:.0f}, max={max(model_scores) if model_scores else 0:.0f}) | "
        f"hook от модели: {n_model_hooks}/{len(moments)} | "
        f"self_contained: {min(model_sc_in):.2f}/{max(model_sc_in):.2f} | "
        f"YamNet-событий всего: {n_events_total}"
    )

    floor = min(min_duration, video_duration)
    n_dropped_short = 0
    n_stretched = 0
    n_capped = 0
    n_with_event = 0
    cleaned = []
    for mo, r in zip(moments, raw):
        if r is None:
            continue
        start = max(0.0, float(mo.start))
        # Absolute composite signal 0..1 (vs whole video). Semantic audio events
        # (laughter/applause/cheering) are the strongest signal, then energy
        # peaks, loudness and speech density.
        has_event = len(r) > 3 and r[3] > 1e-9
        if has_event:
            n_with_event += 1
        if gstats is not None:
            e_rms, e_peak, e_speech, e_event = _abs_components(r, gstats)
            if has_event:
                comp = 0.35 * e_event + 0.30 * e_peak + 0.20 * e_rms + 0.15 * e_speech
            else:
                comp = 0.45 * e_peak + 0.35 * e_rms + 0.20 * e_speech
        else:
            # No global stats (no audio analysis): fall back to neutral.
            comp = 0.5
        # Target length scales with signal: strong moments get longer clips.
        target = min_duration + (max_duration - min_duration) * comp
        # Anchor on a clean, context-giving START (the hook); the END is secondary
        # for this style, so we snap the start to a sentence/intro boundary and run
        # forward from there.
        start = _refine_start(sentences, start, lookback=6.0)
        end = min(start + target, video_duration)
        orig_len = end - start
        if end - start > max_duration:
            end = start + max_duration
            n_capped += 1
        if end - start < min_duration:
            start = max(0.0, end - min_duration)
            n_stretched += 1
        if end - start < min(floor, 15.0) - 0.01:
            n_dropped_short += 1
            continue
        mo.start = round(start, 2)
        mo.end = round(end, 2)

        # ── SELF-CONTAINED GATE (hard) ─────────────────────────────────────
        # A clip that "starts without a hook and nothing makes sense" must never
        # score high, no matter how loud. The model now reports self_contained;
        # we also derive a deterministic signal: is the OPENING speech present
        # and complete (not a fragment dropped in mid-sentence)?
        model_sc = float(getattr(mo, "self_contained", 0.5) or 0.5)
        # Deterministic self-containment proxy: speech present in the first 3s.
        hook_window = 3.0
        sr3 = _signal_for_window(ctx, mo.start, min(mo.start + hook_window, mo.end))
        open_chars = sr3[2]  # speech chars in the opening window
        # If there is essentially no speech at the very start, the clip opens on
        # a lull/fragment -> not self-contained. Penalize, but keep the model's
        # read dominant when it is confident.
        speech_present = open_chars >= 8.0  # ~a short clause
        signal_sc = 0.6 if speech_present else 0.25
        self_contained = round(max(model_sc, 0.5 * model_sc + 0.5 * signal_sc), 3)
        mo.self_contained = self_contained

        # ── HOOK STRENGTH ────────────────────────────────────────────────────
        # Retention is decided in the first seconds. The model's read is the
        # primary source; the deterministic part now rewards a clip whose opening
        # has real ACTIVITY (event/speech), not merely a loud spike — a spike
        # alone is not a hook (it can be a fragment or a jump-scare).
        open_sig = (sr3[1] + sr3[3]) + 0.01 * sr3[2]
        full_sig = (r[1] + r[3]) + 0.01 * r[2]
        open_dur = max(min(mo.start + hook_window, mo.end) - mo.start, 0.1)
        full_dur = max(mo.end - mo.start, 0.1)
        open_density = open_sig / open_dur
        full_density = full_sig / full_dur
        signal_hook = open_density / full_density if full_density > 1e-9 else 0.5
        signal_hook = max(0.0, min(1.0, signal_hook / 2.0))  # ~2x avg -> 1.0
        # A clip with no speech at the start cannot have a great hook: cap it.
        if not speech_present:
            signal_hook = min(signal_hook, 0.4)
        model_hook = float(getattr(mo, "hook_strength", 0.0) or 0.0)
        hook = round(max(model_hook, 0.5 * model_hook + 0.5 * signal_hook), 3)
        mo.hook_strength = hook

        # ── SCORE (absolute + hard gates) ────────────────────────────────────
        # Two paths:
        #   1. model_has_variance → trust the model. Take its virality_score
        #      VERBATIM (no hook/component bonus — the model already factors
        #      them in), then apply the hard caps (sc, hook, det).
        #      Historical lesson: adding (hook - 0.5) · 16 to a model that
        #      ALREADY scored hook 0.95 → base jumps by +8 regardless of
        #      model score. Two Gemini moments at model score 95 and 98,
        #      both with hook 0.95, become 103 and 106 → both capped at 95.
        #      The whole point of `variance is signal` collapses. Fix: don't
        #      double-count.
        #   2. !model_has_variance → deterministic rescoring (no model trust):
        #      compute from comp + (hook - 0.5) · 16 as before, capped at 85.
        if model_has_variance:
            base = float(getattr(mo, "virality_score", 0) or 50)
        else:
            base = 40 + 45 * comp  # 40..85 absolute
            # Fold hook in (a great clip with a weak start is worth less).
            base += (hook - 0.5) * 16.0  # hook 1.0 -> +8, hook 0.0 -> -8

        # Hard cap on the deterministic band:
        #   * No variance + no event     → 85  (deterministic takes over)
        #   * Variance + no event        → 95  (preserve model ranking)
        #   * Variance + high + event    → 100 (full trust)
        det_cap = 85
        model_high = base >= 70 and float(getattr(mo, "virality_score", 0) or 0) >= 80
        if model_high and has_event:
            det_cap = 100
        elif model_has_variance and not has_event:
            # Real differentiation but our local cues don't see an event. Trust
            # the model up to 95 — never pin to 100 without an audio event.
            det_cap = 95
        base = min(base, det_cap)

        # HARD GATES: self_contained / hook_strength absolutely clamp the score,
        # regardless of energy. This is the fix for "incoherent clip scores 100".
        sc_cap = 45 if self_contained < 0.4 else (62 if self_contained < 0.55 else 100)
        hook_cap = 60 if hook < 0.3 else (75 if hook < 0.5 else 100)
        base = min(base, sc_cap, hook_cap)

        mo.virality_score = int(round(max(1, min(100, base))))
        logger.debug(
            f"⚖️  [Constraints] {mo.start:.1f}-{mo.end:.1f}s ({mo.end-mo.start:.0f}с) "
            f"comp={comp:.2f} hook={hook:.2f} (модель={model_hook:.2f}/сигнал={signal_hook:.2f}) "
            f"sc={self_contained:.2f} (модель={model_sc:.2f}/сигнал={signal_sc:.2f}) "
            f"{'+событие ' if has_event else ''}→ score={mo.virality_score}"
        )
        cleaned.append(mo)

    cleaned.sort(key=lambda x: x.virality_score or 0, reverse=True)
    kept = []
    for mo in cleaned:
        overlapped = False
        for k in kept:
            inter = min(mo.end, k.end) - max(mo.start, k.start)
            if inter > 0 and inter > 0.5 * min(mo.end - mo.start, k.end - k.start):
                overlapped = True
                break
        if not overlapped:
            kept.append(mo)

    n_before_dedup = len(cleaned)
    n_after_dedup = len(kept)
    n_capped_to_max = max(0, n_after_dedup - max_moments)
    kept = kept[:max_moments]
    kept.sort(key=lambda x: x.start)  # chronological for display

    # Final distribution of what survived — makes the new features visible.
    if kept:
        sc = [int(m.virality_score or 0) for m in kept]
        hk = [float(getattr(m, "hook_strength", 0.0) or 0.0) for m in kept]
        sct = [float(getattr(m, "self_contained", 0.5) or 0.5) for m in kept]
        durs = [round(m.end - m.start, 1) for m in kept]
        logger.info(
            f"⚙️  [Ограничения] Итог: {len(kept)} моментов | "
            f"score min/avg/max = {min(sc)}/{sum(sc)//len(sc)}/{max(sc)} | "
            f"hook min/avg/max = {min(hk):.2f}/{sum(hk)/len(hk):.2f}/{max(hk):.2f} | "
            f"self_contained min/avg/max = {min(sct):.2f}/{sum(sct)/len(sct):.2f}/{max(sct):.2f} | "
            f"длительность min/max = {min(durs)}/{max(durs)}с"
        )
        logger.info(
            f"⚙️  [Ограничения] Обработка: растянуто {n_stretched}, обрезано {n_capped}, "
            f"отброшено коротких {n_dropped_short}, дедуп {n_before_dedup}→{n_after_dedup}, "
            f"обрезка по max_moments {n_capped_to_max} | с YamNet-событием в окне: {n_with_event}"
        )
        # Top-3 preview so you can eyeball quality without the UI.
        top = sorted(kept, key=lambda x: x.virality_score or 0, reverse=True)[:3]
        for rank, m in enumerate(top, 1):
            logger.info(
                f"⚙️  [Ограничения] ТОП-{rank}: {m.start:.0f}-{m.end:.0f}с "
                f"score={m.virality_score} hook={getattr(m, 'hook_strength', 0.0):.2f} "
                f"sc={getattr(m, 'self_contained', 0.5):.2f} "
                f"тип={getattr(m, 'content_type', '?')} hook_text=\"{(getattr(m, 'hook', '') or '')[:60]}\""
            )
    else:
        logger.warning("⚙️  [Ограничения] Итог: 0 моментов после фильтрации!")
    return kept

class DetectionPipeline:
    """Orchestrates 3-stage GPU pipeline for moment detection.
    
    GPU-first: uses GPU when CUDA available, falls back to legacy CPU pipeline otherwise.
    """

    async def _run_cross_modal(
        self, ctx: "Stage1Context", video_path: str, progress_callback: Optional[Callable] = None
    ) -> None:
        """Stage 1.5 — populate ctx.face_clusters + ctx.speaker_segments.

        Two parallel tracks:
            A) `face_identity.cluster(face_timeline)` — DBSCAN over
               buffalo_l embeddings, GPU hours-mine.
            B) `speaker_diarizer.diarize(waveform_16k)` — pyannote-audio 4.x,
               needs CLIPFORGE_HF_TOKEN.

        Both modules fail gracefully (each returns [] on any error). The
        cross-modal `anchor(...)` then joins speaker turns with face
        clusters, producing `SpeakerSegment` rows that the LLM prompt
        surfaces as the PEOPLE / SPEAKERS section.

        VRAM sequencing: whisper + yolo are already unloaded at this point.
        We sequentially load face_identity (~1 GB), then diarizer (~2 GB),
        then unload both before Stage 2. We re-extract the audio waveform
        once via a small ffmpeg pipe (no full 16 kHz re-decode of the original
        Whisper result — pyannote wants 16 kHz mono as plain float32).
        """
        from backend.services import face_identity, speaker_diarization, cross_modal

        # 1. face clustering
        try:
            if progress_callback:
                await progress_callback({
                    "stage": 1, "step": "face_identity_load",
                    "progress": 0.605,
                    "detail": "загрузка buffalo_l (insightface)",
                })
            clusters = await asyncio.to_thread(
                face_identity.face_identity.cluster,
                ctx.face_timeline,
                video_path,
            )
            ctx.face_clusters = clusters
            if progress_callback:
                await progress_callback({
                    "stage": 1, "step": "face_identity_done",
                    "progress": 0.62,
                    "detail": f"кластеров={len(clusters)} ({sum(len(c.track_ids) for c in clusters)} треков)",
                })
        except Exception as e:
            logger.warning(f"👤 [FaceID] неожиданная ошибка ({e}) — без лиц")
            ctx.face_clusters = []
        finally:
            vram_manager.unload_model("face_identity")

        # 2. speaker diarization: re-decode audio once via ffmpeg (cheap).
        try:
            if progress_callback:
                await progress_callback({
                    "stage": 1, "step": "diarization_extract",
                    "progress": 0.625,
                    "detail": "ffmpeg → wav 16kHz mono",
                })
            import subprocess, tempfile, os
            wav_path = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ).name
            try:
                _ffmpeg_to_wav(video_path, wav_path)
                import numpy as np
                import soundfile as sf
                wav, sr = sf.read(wav_path, dtype="float32", always_2d=False)
                if wav.ndim > 1:
                    wav = wav.mean(axis=0)
                if progress_callback:
                    await progress_callback({
                        "stage": 1, "step": "diarization_run",
                        "progress": 0.635,
                        "detail": "pyannote-audio 4.x (если есть HF токен)",
                    })
                turns = speaker_diarization.speaker_diarizer.diarize(wav, sr=int(sr))
            finally:
                if os.path.exists(wav_path):
                    os.unlink(wav_path)
            if turns:
                speaker_count = len({t.speaker_id for t in turns})
                if progress_callback:
                    await progress_callback({
                        "stage": 1, "step": "cross_modal_anchor",
                        "progress": 0.645,
                        "detail": f"{len(turns)} turns, {speaker_count} спикеров → anchor к лицам",
                    })
                ctx.speaker_segments = cross_modal.anchor(
                    speaker_turns=turns,
                    face_timeline=ctx.face_timeline,
                    face_clusters=ctx.face_clusters,
                    transcript=ctx.transcript,
                )
            else:
                ctx.speaker_segments = []
        except Exception as e:
            logger.warning(f"🤝 [CrossModal] неожиданная ошибка ({e}) — без спикеров")
            ctx.speaker_segments = []
        finally:
            vram_manager.unload_model("diarization")

        if progress_callback:
            await progress_callback({
                "stage": 1, "step": "cross_modal_done", "progress": 0.65,
                "detail": f"кластеров={len(ctx.face_clusters)}, "
                          f"speakers={len(ctx.speaker_segments)}",
            })

    def _should_use_gpu(self) -> bool:
        """Determine if GPU pipeline should be used.
        
        Returns:
            True if GPU should be used, False for CPU legacy fallback
        """
        from backend.gpu_config import USE_GPU_PIPELINE
        
        cfg = USE_GPU_PIPELINE.lower()
        if cfg == "false":
            return False
        # "true" or "auto" both use GPU if CUDA available
        return vram_manager.is_gpu

    async def _run_llm_director(
        self,
        ctx: Stage1Context,
        user_instructions: str,
        min_duration: int,
        max_duration: int,
        max_moments: int,
        progress_callback: Optional[Callable] = None,
        preset_id: str = "default",
    ) -> DirectorOutput:
        """Stage 2: pre-flight Gemini, build context shape, run director.

        Extracted into its own method so the pre-flight → context-shape → director
        flow is independently testable without spinning up the whole pipeline.

        Order matters:
          1. Pre-flight Gemini FIRST. If Gemini is configured but unreachable
             (region block, dead proxy, missing socksio, quota) we should not
             waste time building chunks for it.
          2. Pick context shape according to the director:
                * Gemini → build_single_context (whole video in one prompt).
                * Qwen3  → build_chunks (8K context window forces chunking).
          3. Run the actual director. If Gemini fails mid-flight after a
             healthy pre-flight, rebuild chunks for the Qwen fallback.
        """
        logger.info("▶️  [Этап 2/3] Начало ИИ-анализа...")
        logger.info("")

        # ── 1. pre-flight Gemini ──────────────────────────────────────────────
        # Gemini 2.5 Flash holds 1M input tokens / 250K TPM. A 30-min Russian
        # video is ~5000 tokens total — it fits ONE request. Single context
        # gives the model the whole timeline and lets it reason across it
        # (e.g. a late payoff that references an early setup).
        use_gemini = gemini_is_configured()
        gemini_ok = False
        if use_gemini:
            if progress_callback:
                await progress_callback({"stage": 2, "step": "gemini_preflight", "progress": 0.63})
            logger.info(f"🛰️  [Этап 2/3] Пре-полётная проверка Gemini {GEMINI_MODEL}...")
            gemini_ok = await asyncio.to_thread(gemini_director.check_health)
            if gemini_ok:
                logger.info(f"🛰️  [Gemini] Доступен → единый контекст (250K TPM, 1M токенов на запрос)")
            else:
                logger.warning("🛰️  [Gemini] Пре-полётная проверка не прошла → локальный Qwen3-8B")

        if use_gemini and gemini_ok:
            logger.info(f"🛰️  [Этап 2/3] Режиссёр: Gemini {GEMINI_MODEL} (single context), резерв — Qwen3-8B")
        elif use_gemini:
            logger.info("🧠 [Этап 2/3] Режиссёр: Qwen3-8B (локально) — Gemini недоступен")
        else:
            logger.info("🧠 [Этап 2/3] Режиссёр: Qwen3-8B (локально) — Gemini не настроен")

        if progress_callback:
            await progress_callback({"stage": 2, "step": "context_building", "progress": 0.65})

        # ── 2. pick + build context shape ─────────────────────────────────────
        chunk_analyze_time = 90  # ~60-120s per chunk on RTX 5060 (Qwen3-8B Q4)
        if use_gemini and gemini_ok:
            context_input: str | list[str] = await asyncio.to_thread(
                context_builder.build_single_context, ctx, user_instructions
            )
            est_llm_time = 60  # single Gemini call (incl. reasoning overhead)
            logger.info(f"🧠 [LLM] Ожидаемое время анализа: ~{est_llm_time}с (single Gemini call)")
        else:
            context_input = await asyncio.to_thread(
                context_builder.build_chunks, ctx, user_instructions
            )
            est_llm_time = len(context_input) * chunk_analyze_time
            if len(context_input) > 1:
                est_llm_time += 20  # +20s for global re-rank pass
            logger.info(f"🧠 [LLM] Ожидаемое время анализа: ~{est_llm_time}с ({len(context_input)} чанков)")

        if progress_callback:
            await progress_callback({"stage": 2, "step": "llm_analysis", "progress": 0.70})

        # ── 3. progress callback wrapper (sync → async) ───────────────────────
        _loop = asyncio.get_event_loop()
        def _llm_progress(chunk_i: int, total: int, phase: str = "chunk"):
            prog = 0.70 + (chunk_i / max(total, 1)) * 0.14
            step_name = "llm_chunk" if phase == "chunk" else "llm_consolidate"
            coro = progress_callback({
                "stage": 2,
                "step": step_name,
                "progress": prog,
                "detail": (
                    "Единый контекст" if total <= 1 else f"Чанк {chunk_i}/{total}"
                ),
            }) if progress_callback else None
            if coro is not None:
                asyncio.run_coroutine_threadsafe(coro, _loop)

        # ── 4. run the chosen director ────────────────────────────────────────
        director_output = None
        if use_gemini and gemini_ok:
            try:
                director_output = await asyncio.to_thread(
                    gemini_director.analyze, context_input, user_instructions, _llm_progress,
                    min_duration, max_duration, max_moments, preset_id
                )
            except Exception as e:
                # Pre-flight said OK but real call failed (proxy hiccup,
                # quota exhausted mid-batch). Fall back to Qwen, but Qwen
                # needs CHUNKS — single context would blow its 8K window.
                logger.warning(
                    f"⚠️  [Gemini] Пре-полёт OK, но реальный вызов провалился "
                    f"({type(e).__name__}: {e}). Перестраиваю контекст под Qwen..."
                )
                context_input = await asyncio.to_thread(
                    context_builder.build_chunks, ctx, user_instructions
                )
                director_output = None

        if director_output is None:
            if use_gemini and gemini_ok:
                logger.info("🧠 [Qwen3] Резервный анализ локально...")
            director_output = await asyncio.to_thread(
                llm_director.analyze, context_input, user_instructions, _llm_progress,
                min_duration, max_duration, max_moments, preset_id
            )

        vram_manager.unload_all()  # Safety flush
        if director_output is not None:
            logger.info(
                f"✅  [Этап 2/3] Найдено {len(director_output.moments)} моментов"
            )
        return director_output

    async def run(
        self,
        video_path: str,
        user_instructions: str = "",
        max_moments: int = 10,
        min_duration: int = 30,
        max_duration: int = 90,
        progress_callback: Optional[Callable] = None,
        preset_id: str = "default",
    ) -> DirectorOutput:
        """Run 3-stage GPU pipeline for moment detection.

        Args:
            video_path: Path to video file
            user_instructions: Optional user analysis instructions
            max_moments: Maximum number of moments to return
            min_duration: Minimum moment duration in seconds
            max_duration: Maximum moment duration in seconds
            progress_callback: Optional async callback for progress updates
            preset_id: Content preset (#4). 'default' is no-op; others inject
                targeted LLM rules for films_anime/streams/youtube_cuts.

        Returns:
            DirectorOutput with detected moments
        """
        use_gpu = self._should_use_gpu()

        if not use_gpu:
            logger.warning("GPU not available — using legacy CPU pipeline")
            # Import legacy pipeline only when needed
            from backend.services.scene_detector import detect_moments_from_video
            from backend.services.speech_scorer import analyze_speech_content
            
            # Legacy CPU pipeline (existing code path)
            if progress_callback:
                await progress_callback({"stage": "legacy", "step": "analyzing", "progress": 0.5})
            
            speech_scores = analyze_speech_content(video_path)
            
            # Get video duration
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_duration = total_frames / fps
            cap.release()
            
            # Legacy detection returns moments in old format
            # We need to wrap it in DirectorOutput for API compatibility
            legacy_moments = detect_moments_from_video(
                video_path,
                "temp_id",
                video_duration,
                speech_scores,
                max_moments,
                min_duration,
                max_duration
            )
            
            # Convert to DirectorOutput format (simplified, no LLM analysis)
            from backend.schemas.moment_instruction import MomentInstruction, SubtitleMode
            moments = []
            for m in legacy_moments:
                moments.append(MomentInstruction(
                    start=m.start,
                    end=m.end,
                    hook="Interesting moment detected",
                    virality_score=m.score * 100,
                    content_type="explanation",
                    subtitle_mode=SubtitleMode.ru_only,
                    reasoning=m.reason or "CPU legacy detection",
                    camera_plan=[],
                ))
            
            return DirectorOutput(
                moments=moments,
                total_analyzed=len(moments),
                language_detected="unknown"
            )

        import time
        from pathlib import Path
        
        start_time = time.time()
        video_name = Path(video_path).name
        
        # Get video info for estimates
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps
        cap.release()
        
        video_duration_min = video_duration / 60.0
        
        # Time estimates for RTX 5060 (8GB). Stage 1 is dominated by YOLO face
        # tracking (roughly real-time-ish per sampled frame); Stage 2 by the LLM.
        # These are rough upper bounds — actual time varies with scene complexity.
        if video_duration_min <= 30:
            est_stage1 = "5-10мин"
            est_stage2 = "2-4мин"
            est_total = "7-14 минут"
        elif video_duration_min <= 60:
            est_stage1 = "10-20мин"
            est_stage2 = "4-7мин"
            est_total = "15-27 минут"
        else:
            est_stage1 = "20-35мин"
            est_stage2 = "7-12мин"
            est_total = "27-47 минут"
        
        gpu_mode = "GPU (CUDA)" if vram_manager.is_gpu else "CPU (резервный)"
        logger.info(f"🚀 [Детекция] Запуск GPU-пайплайна для видео: {video_name} ({video_duration_min:.1f} мин)")
        logger.info(f"📊 [Детекция] Режим: {gpu_mode}")
        logger.info(f"⏱️  [Детекция] Примерное время: ~{est_total} (Этап 1: {est_stage1} + Этап 2: {est_stage2})")
        logger.info("")

        # ─── STAGE 1: Data Collection ────────────────────────────────────────
        stage1_start = time.time()
        logger.info("▶️  [Этап 1/3] Начало сбора данных...")
        logger.info("")
        
        if progress_callback:
            await progress_callback({"stage": 1, "step": "transcription", "progress": 0.05})

        transcript = await asyncio.to_thread(whisper_gpu.transcribe, video_path)
        vram_manager.unload_all()  # Safety flush
        
        # Count words and segments for granular progress detail
        total_words = sum(len(seg.text.split()) for seg in transcript) if transcript else 0
        total_segments = len(transcript) if transcript else 0

        if progress_callback:
            await progress_callback({
                "stage": 1,
                "step": "transcription_done",
                "progress": 0.28,
                "detail": f"{total_words} слов, {total_segments} сегментов"
            })

        if progress_callback:
            await progress_callback({"stage": 1, "step": "face_detection", "progress": 0.30})

        face_timeline = await asyncio.to_thread(face_detector.detect_faces_timeline, video_path)
        vram_manager.unload_all()  # Safety flush
        
        face_count = len(face_timeline.unique_face_ids) if face_timeline else 0

        if progress_callback:
            await progress_callback({
                "stage": 1,
                "step": "yolo_done",
                "progress": 0.48,
                "detail": f"{face_count} лиц"
            })

        if progress_callback:
            await progress_callback({"stage": 1, "step": "audio_analysis", "progress": 0.50})

        audio_analysis = await asyncio.to_thread(audio_analyzer.analyze, video_path)
        
        # Extract peak count from audio analysis
        peak_count = len(audio_analysis.peaks) if hasattr(audio_analysis, 'peaks') and audio_analysis.peaks else 0
        
        if progress_callback:
            await progress_callback({
                "stage": 1,
                "step": "audio_done",
                "progress": 0.57,
                "detail": f"{peak_count} пиков"
            })
        
        stage1_time = time.time() - stage1_start
        logger.info("")
        logger.info(f"✅  [Этап 1/3] Завершён за {stage1_time:.1f}с")
        logger.info("")

        ctx = Stage1Context(
            transcript=transcript,
            face_timeline=face_timeline,
            audio_analysis=audio_analysis,
            video_duration=video_duration,
            video_path=video_path,
        )

        # ─── STAGE 1.5: Cross-modal identity (OPTIONAL) ──────────────────────
        # Runs AFTER whisper + YOLO unload so we never exceed VRAM.
        # Both modules have graceful degradation: missing models, missing
        # HF token, or import errors → empty list. Nothing in Stage 2 breaks.
        await self._run_cross_modal(ctx, video_path, progress_callback)

        if progress_callback:
            await progress_callback({"stage": 1, "step": "done", "progress": 0.60})

        # ─── STAGE 2: LLM Director ───────────────────────────────────────────
        stage2_start = time.time()
        director_output = await self._run_llm_director(
            ctx, user_instructions, min_duration, max_duration, max_moments, progress_callback, preset_id=preset_id,
        )
        stage2_time = time.time() - stage2_start
        logger.info("")
        logger.info(f"✅  [Этап 2/3] Завершён за {stage2_time:.1f}с")
        logger.info("")

        if progress_callback:
            await progress_callback({"stage": 2, "step": "done", "progress": 0.90})

        # ─── STAGE 3: Done (rendering happens per-clip via /render endpoint) ─
        logger.info("▶️  [Этап 3/3] Подготовка результатов...")
        logger.info("")
        
        if progress_callback:
            await progress_callback({"stage": 3, "step": "done", "progress": 1.0})

        total_time = time.time() - start_time
        logger.info(f"✅  [Этап 3/3] Завершён за 0.5с")
        logger.info("")
        # Enforce Detection Settings deterministically (LLM often ignores them).
        director_output.moments = _enforce_constraints(
            director_output.moments, min_duration, max_duration, max_moments, video_duration, ctx,
        )

        # Populate `MomentInstruction.speakers` from Stage 1.5 cross-modal
        # output. Populating AFTER _enforce_constraints because that step
        # resnaps moments' start/end times; using the post-reflow times
        # means the speaker list reflects the final moment, not the raw
        # LLM-suggested one. Empty list when cross-modal produced nothing.
        if ctx.speaker_segments:
            from backend.services import cross_modal
            for mo in director_output.moments:
                mo.speakers = cross_modal.speakers_in_range(
                    ctx.speaker_segments, mo.start, mo.end,
                )

        logger.info("="*60)
        logger.info(f"🎉 [Детекция] Готово! Найдено {len(director_output.moments)} моментов за {total_time:.1f}с")
        
        # Log top moments
        if director_output.moments:
            top_moment = director_output.moments[0]
            logger.info(f"🏆 Топ момент: \"{top_moment.hook}\" (вирусность: {top_moment.virality_score:.0f}/100)")
        
        logger.info("="*60)
        logger.info("")
        
        return director_output


# Global singleton instance
detection_pipeline = DetectionPipeline()