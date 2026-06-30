"""Plan + render Pillow subtitle overlays for a clip.

Pipeline:

  1. ``generate_pillow_subtitles`` transcribes the clip with the same
     whisper-large-v3 model the legacy ASS path uses, splits the
     transcript into chunks (style-specific chunk size), and emits:

     * one PNG file per (chunk, optional active word) timestamp pair,
       rendered by :mod:`pillow_subtitle_renderer`;
     * a list of :class:`SubtitleOverlay` records telling the caller
       which PNG to load as ``-i N`` in ffmpeg and which ``enable``
       window to use during composite.

  2. ``compose_overlay_filter`` writes the ffmpeg ``filter_complex``
     fragment that stitches those PNGs onto a base video, one overlay
     at a time, each only enabled during its time window.

The resulting pipeline has the same effects ordering as the legacy ASS
path: blur-bg → mirror → color-correction → subtitles → banner → vout.
Pillow replaces only step 4.

A new env switch ``CLIPFORGE_PILLOW_SUBS`` (default ``1``) lets you
flip back to the legacy libass renderer for A/B comparison.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

from PIL import Image

from .pillow_subtitle_renderer import render_text_to_image, save_png

logger = logging.getLogger(__name__)


# Style-specific chunk sizes mirrored from speech_scorer.py
# (chunk_size_map) so the visual rhythm matches the ASS path.
_CHUNK_SIZE_FOR_STYLE = {
    "karaoke": 2,
    "bold": 2,
    "neon": 2,
    "minimal": 3,
    "cinematic": 2,
    "hormozi": 3,
    "highlight": 3,
}


@dataclass
class SubtitleOverlay:
    """One PNG → map to a specific (start, end) window and (x, y)
    on a ``(canvas_w, canvas_h)`` canvas. ``highlight_word_idx`` is the
    karaoke-style active-word index (-1 = no highlight)."""

    png_path: str
    start: float
    end: float
    highlight_word_idx: int = -1

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ─── Transcription (reused from speech_scorer.ass path) ─────────────────────


def _transcribe_with_words(video_path: str) -> List[dict]:
    """Re-transcribe the clip with the same GPU whisper-large-v3 used
    elsewhere in the pipeline. Returns segments with per-word
    ``start`` / ``end`` timelines."""
    try:
        from backend.services.whisper_gpu import whisper_gpu
        segs = whisper_gpu.transcribe(video_path)
        return [
            {
                'start': s.start,
                'end': s.end,
                'text': s.text,
                'words': [
                    {'word': w.word, 'start': w.start, 'end': w.end}
                    for w in (s.words or [])
                ],
            }
            for s in segs
        ]
    except Exception as e:
        logger.warning(
            f"[PillowSubs] GPU transcription failed ({e}); falling back "
            f"to legacy base model."
        )
        try:
            from backend.services.speech_scorer import transcribe_video
            return transcribe_video(video_path)
        except Exception as ee:
            logger.error(f"[PillowSubs] ALL transcription failed: {ee}")
            return []


# ─── Style-aware chunker (mirrors ASS path semantics) ───────────────────────


def _chunk_segment_words(
    segment: dict,
    chunk_size: int,
    style: str,
) -> List[dict]:
    """Slice segment into chunks of ``chunk_size`` words each. Returns
    a list of ``{start, end, text, words, highlight_word_idx}``.

    For ``karaoke`` we additionally emit one chunk per active-word
    interval so the renderer can paint the active word in yellow."""
    words = segment.get("words") or []
    if not words:
        # No word-level timing — single chunk holding the full segment.
        return [{
            'start': segment['start'],
            'end': segment['end'],
            'text': (segment.get('text') or '').strip().upper(),
            'words': [],
            'highlight_word_idx': -1,
        }]

    # Group into N-word chunks based on style.
    n_chunks = (len(words) + chunk_size - 1) // chunk_size
    chunks: List[List[dict]] = [[] for _ in range(n_chunks)]
    for i, w in enumerate(words):
        chunks[i // chunk_size].append(w)

    out: List[dict] = []
    for ci, ch_words in enumerate(chunks):
        if not ch_words:
            continue
        text = " ".join(w["word"].strip().upper() for w in ch_words).strip()
        if not text:
            continue
        chunk_start = ch_words[0]['start']
        chunk_end = ch_words[-1]['end']

        if style == "karaoke" and len(ch_words) > 1:
            # Emit one entry per active-word interval for the highlight.
            for active_i in range(len(ch_words)):
                word_start = ch_words[active_i]['start']
                word_end = (
                    ch_words[active_i + 1]['start']
                    if active_i + 1 < len(ch_words)
                    else chunk_end
                )
                if word_end <= word_start:
                    word_end = word_start + 0.05
                out.append({
                    'start': word_start,
                    'end': word_end,
                    'text': text,
                    'words': ch_words,
                    'highlight_word_idx': active_i,
                })
        else:
            out.append({
                'start': chunk_start,
                'end': chunk_end,
                'text': text,
                'words': ch_words,
                'highlight_word_idx': -1,
            })
    return out


# ─── Pipeline entry point ───────────────────────────────────────────────────


def generate_pillow_subtitles(
    video_path: str,
    output_dir: Path,
    style: str,
    *,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> List[SubtitleOverlay]:
    """Render subtitle PNGs for a clip into ``output_dir``.

    Returns a list of :class:`SubtitleOverlay` ready for ffmpeg
    ``overlay=enable='between(t,start,end)'``. On transcription or
    render failure returns an empty list — the calling pipeline falls
    back to ``null`` (no-op) in that case.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    style = style or "karaoke"
    if style not in _CHUNK_SIZE_FOR_STYLE:
        logger.warning(f"[PillowSubs] unknown style '{style}', falling back to 'karaoke'")
        style = "karaoke"

    logger.info(f"[PillowSubs] transcribing for Pillow subtitle render (style={style})")
    segments = _transcribe_with_words(video_path)
    if not segments:
        return []

    chunk_size = _CHUNK_SIZE_FOR_STYLE[style]
    overlays: List[SubtitleOverlay] = []
    idx = 0
    for seg in segments:
        for chunk in _chunk_segment_words(seg, chunk_size, style):
            img: Image.Image = render_text_to_image(
                chunk['text'],
                style,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                highlight_word_idx=(
                    chunk['highlight_word_idx']
                    if chunk['highlight_word_idx'] and chunk['highlight_word_idx'] >= 0
                    else None
                ),
            )
            png_path = output_dir / f"sub_{idx:05d}.png"
            save_png(img, png_path)
            overlays.append(SubtitleOverlay(
                png_path=str(png_path),
                start=float(chunk['start']),
                end=float(chunk['end']),
                highlight_word_idx=int(chunk['highlight_word_idx'] or -1),
            ))
            idx += 1

    # Sidecar JSON for debugging: covers timings + styles without
    # having to re-parse every PNG filename.
    manifest_path = output_dir / "subs_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "style": style,
                "canvas_w": canvas_w,
                "canvas_h": canvas_h,
                "overlays": [o.to_dict() for o in overlays],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    logger.info(
        f"[PillowSubs] rendered {len(overlays)} overlay PNGs (style={style}) into {output_dir}"
    )
    return overlays


# ─── ffmpeg filter composer ─────────────────────────────────────────────────


def compose_overlay_filter(
    overlays: List[SubtitleOverlay],
    incoming_label: str = "[v3]",
    first_input_idx: int = 2,
) -> str:
    """Build the ffmpeg ``filter_complex`` fragment that overlays N PNGs
    on top of a base video. Each PNG is enabled only during its
    ``between(t, start, end)`` window so the rest of the timeline
    shows the bare video.

    Inputs are expected to be supplied by the caller. Layout::

        [0:v]            ... (the existing pre-subtitle chain)            [v3]
        [2:v]null                                                        [v_pre]
        [v_pre][3:v]overlay=enable='between(t,...)':x=0:y=0              [v_a]
        [v_a][4:v]overlay=enable='between(t,...)':x=0:y=0               [v_b]
        ...                                                              [v4]

    ``first_input_idx`` is the ffmpeg ``-i`` index of the first
    subtitle PNG. Defaults to 2 (assumes video at index 0, no
    banner — bump to 3 when a banner is also in the chain).

    Returns a list of filter chains joined by ';' — callers SHOULD
    drop the trailing ``[v4]null`` they would normally append after
    step 4, because this function already produces ``[v4]``.
    """
    if not overlays:
        return f"{incoming_label}null[v4]"

    parts: List[str] = []
    # Initial chain: v3 → v_pre (just a no-op rename so we can
    # chain overlays one after another).
    parts.append(f"{incoming_label}null[v_pre]")

    last = "[v_pre]"
    for i, ov in enumerate(overlays):
        png_input_idx = first_input_idx + i
        next_label = f"[v_sub_{i}]"
        # Position: PNG is the same size as the video canvas, so
        # x=0:y=0 covers the full frame. PNG itself is transparent
        # except where text is rendered.
        parts.append(
            f"{last}[{png_input_idx}:v]"
            f"overlay=enable='between(t,{ov.start:.3f},{ov.end:.3f})':"
            f"x=0:y=0{next_label}"
        )
        last = next_label

    parts.append(f"{last}null[v4]")
    return ";".join(parts)
