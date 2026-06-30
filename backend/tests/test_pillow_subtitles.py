"""Tests for the Pillow subtitle renderer + overlay filter composer.

We deliberately exercise the renderer against the actual installed
Arial Bold font (if present) and against the Pillow default fallback
when it isn't. Either path should produce a non-empty RGBA image with
the requested canvas size and at least one filled pixel.

Anti-pixelation regression checks: count the number of distinct
alpha values that survive the Gaussian-blur glow. If the renderer was
producing hard 1-bit anti-aliased output (which is exactly what we
want to AVOID), we'd see only ~5-10 distinct alphas per style. The
target is >150 for any glow-style, which is the threshold Pillow's
LANCZOS resampling + Gaussian blur reliably crosses.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image

from backend.services.pillow_subtitle_renderer import (
    STYLE_NAMES,
    SubtitleStyle,
    render_text_to_image,
    save_png,
    style_for,
)
from backend.services.subtitle_overlay import (
    SubtitleOverlay,
    compose_overlay_filter,
    _chunk_segment_words,
)


# Force-load all 7 styles to ensure the table is complete and every
# deploy ships the same set the UI's <SubtitleStylePicker> exposes.
def test_all_seven_styles_render():
    """Every documented style name must produce a valid RGBA canvas at
    the requested size — no exceptions, no missing config."""
    names = ["karaoke", "bold", "neon", "minimal", "cinematic", "hormozi", "highlight"]
    expected = set(STYLE_NAMES)
    assert set(names) == expected, f"style name drift: doc={names}, code={list(STYLE_NAMES)}"

    for n in names:
        img = render_text_to_image("TEST HELLO", n, 1080, 1920)
        assert img.size == (1080, 1920), n
        assert img.mode == "RGBA", n
        # Every style should draw SOMETHING on a non-empty string.
        nonblank = sum(1 for px in img.getdata() if px[3] > 0)
        assert nonblank > 500, (n, "empty render", nonblank)


def test_empty_text_returns_transparent_canvas():
    img = render_text_to_image("", "bold", 1080, 1920)
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"
    nonblank = sum(1 for px in img.getdata() if px[3] > 0)
    assert nonblank == 0, "empty text leaked pixels"


def test_glow_styles_have_halo_blur():
    """The whole point of switching to Pillow: neon/hormozi/karaoke
    styles should produce a soft halo, not just a hard outline. With
    a Glow_radius > 0 and GaussianBlur, the number of distinct alpha
    values in the rendered image should easily exceed 30 even for a
    short string; below that means the blur step is being skipped."""
    for n in ("karaoke", "bold", "neon", "hormozi", "minimal", "cinematic", "highlight"):
        img = render_text_to_image("GLOW CHECK", n, 1080, 1920)
        alphas = {px[3] for px in img.getdata() if px[3] > 0}
        # minimal/cinematic/highlight declare glow_radius=0, so they're
        # allowed to have low alpha-step counts. The other 4 must
        # hit the soft-blur signature.
        if style_for(n).glow_radius > 0:
            assert len(alphas) > 30, (
                f"{n} appears to have flat anti-aliased edges instead "
                f"of a Gaussian halo — only {len(alphas)} distinct "
                f"alpha values"
            )


def test_highlight_word_idx_repositions_word():
    """Karaoke highlight: active word painted at a HIGHLIGHT colour,
    separate from the rest. We verify by isolating the rendered image
    into RGB channels and confirming at least one pixel with the
    highlight colour (yellow ~ (255, 230, 0)) is present."""
    img = render_text_to_image(
        "ALPHA BETA GAMMA", "karaoke",
        canvas_w=1080, canvas_h=1920,
        highlight_word_idx=1,         # BETA is yellow
        highlight_color=(255, 230, 0),
    )
    found = False
    for r, g, b, a in img.getdata():
        if a > 100 and r > 200 and g > 200 and b < 80:
            found = True
            break
    assert found, "active-word highlight not painted in yellow"


def test_save_png_returns_readable_file():
    img = render_text_to_image("HELLO", "bold", 1080, 1920)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "frame.png"
        save_png(img, out)
        assert out.exists()
        # Loading it back should yield equivalent pixel data.
        with Image.open(out) as loaded:
            assert loaded.size == img.size
            assert loaded.mode == "RGBA"


def test_chunk_segment_words_karaoke_emits_per_active_word():
    """Karaoke emits one Dialogue per active word so the renderer can
    paint the active word in yellow. Without that the highlight
    effect wouldn't work."""
    seg = {
        "start": 0.0, "end": 2.0,
        "text": "A B C",
        "words": [
            {"word": "A", "start": 0.0, "end": 0.5},
            {"word": "B", "start": 0.6, "end": 1.0},
            {"word": "C", "start": 1.1, "end": 1.5},
        ],
    }
    out = _chunk_segment_words(seg, chunk_size=2, style="karaoke")
    # chunked into [[A,B],[C]] — first chunk is 2-word, so emits
    # one entry per active word (2 entries); second chunk is single
    # word, no highlight sweep (1 entry).
    assert len(out) == 3, out
    # First two should be highlighted; C should have no highlight.
    assert [c["highlight_word_idx"] for c in out] == [0, 1, -1]


def test_chunk_segment_words_other_styles_use_chunk_only():
    seg = {
        "start": 0.0, "end": 4.0,
        "text": "A B C D",
        "words": [
            {"word": "A", "start": 0.0, "end": 0.5},
            {"word": "B", "start": 0.6, "end": 1.0},
            {"word": "C", "start": 1.1, "end": 1.5},
            {"word": "D", "start": 1.6, "end": 2.0},
        ],
    }
    out = _chunk_segment_words(seg, chunk_size=2, style="bold")
    assert len(out) == 2, out    # 2 chunks, no per-word highlighting
    assert [c["highlight_word_idx"] for c in out] == [-1, -1]


def test_compose_overlay_filter_empty_returns_noop():
    out = compose_overlay_filter([])
    assert out == "[v3]null[v4]", out


def test_compose_overlay_filter_chain_correct_inputs():
    ovls = [
        SubtitleOverlay(png_path="/tmp/sub1.png", start=0.5, end=2.0, highlight_word_idx=-1),
        SubtitleOverlay(png_path="/tmp/sub2.png", start=2.0, end=4.0, highlight_word_idx=0),
        SubtitleOverlay(png_path="/tmp/sub3.png", start=4.0, end=6.0, highlight_word_idx=2),
    ]
    filt = compose_overlay_filter(ovls, first_input_idx=2)
    # Each overlay references the next PNG input idx.
    assert "[2:v]" in filt
    assert "[3:v]" in filt
    assert "[4:v]" in filt
    # Each overlay's enable-window is present, with 3-decimal precision.
    assert "between(t,0.500,2.000)" in filt
    assert "between(t,2.000,4.000)" in filt
    assert "between(t,4.000,6.000)" in filt
    # Final output must reach [v4] so the existing banner stage can
    # consume it.
    assert filt.endswith("[v4]")
    # Sanity: filter chain has 1 (initial) + N (overlays) + 1 (terminal) parts.
    assert len(filt.split(";")) == 1 + len(ovls) + 1
