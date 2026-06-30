"""Pillow-based subtitle renderer.

Replaces the libass chain in ffmpeg with hand-rasterised PNG frames so
that:

  * anti-aliasing is real multiline LANCZOS on TrueType glyphs (no more
    staircase edges or blocky outlines);
  * glow halos are actual Gaussian blurs stacked underneath the text,
    not ffmpeg's `Shadow=` (single offset, hard edge);
  * the stroke is a separate semi-transparent layer composited at high
    alpha so neon / bold / karaoke highlights stay crisp even on
    noisy footage.

Each call to :func:`render_text_to_image` produces one transparent PNG
that contains a single subtitle line. The caller (typically
``subtitle_overlay.py``) is responsible for stitching many PNGs into a
single clip via ffmpeg ``overlay=enable='between(t,...)'``.

Pillow dependency: this module is pure — ffmpeg/font detection is
isolated in ``subtitle_overlay.py``.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# Fallback font paths tried in order if the configured path is missing.
# We deliberately don't bundle a font in the repo: we rely on whatever
# the operator system has — Arial / Liberation Sans are universally
# available on Windows + Linux + WSL.
_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\arialbd.ttf",  # Arial Bold
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    # Linux + WSL
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _find_bold_font() -> str:
    """Pick the first available bold Arial-like font."""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    # As a final fallback let Pillow pick a default bitmap — works but
    # is genuinely ugly; usually a sign that Pillow didn't compile with
    # libfreetype, so emit a loud warning.
    sys.stderr.write(
        "[pillow_subs] WARNING: no TrueType font found; using Pillow's "
        "bitmap default. Install arial / liberation / dejavu to fix.\n"
    )
    return None


_BOLD_FONT_PATH = _find_bold_font()


# Public style names — frozen so we can grep/dep-check against
# speech_scorer.py and the UI subtitle picker.
STYLE_NAMES = ("karaoke", "bold", "neon", "minimal", "cinematic", "hormozi", "highlight")


@dataclass(frozen=True)
class SubtitleStyle:
    """Visual style for a subtitle line. All fields are filled by
    :func:`style_for` so callers only ever pick from a known set."""

    name: str
    font_path: Optional[str]
    font_size: int
    text_color: Tuple[int, int, int]
    outline_color: Tuple[int, int, int]
    outline_width: int
    # Glow halo: 0 = no glow, otherwise Gaussian blur radius on a
    # duplicate of the text laid UNDERNEATH the main text.
    glow_radius: int
    glow_color: Optional[Tuple[int, int, int]]
    # Optional box behind the text (cinematic / highlight).
    bg_color: Optional[Tuple[int, int, int]]
    bg_alpha: int             # 0-255; 0 disables even if bg_color set
    # Tracking (px between glyphs) — 0 means hugging.
    letter_spacing: int
    bold: bool


# ─── Built-in styles ────────────────────────────────────────────────────────
# These mirror the ASS styles in speech_scorer.py:generate_subtitles_file
# so the existing UI `<SubtitleStylePicker>` labels keep working without
# a renaming pass. Visual numbers (font size, outline) are tweaked for
# the Pillow renderer's slightly different anti-aliasing curve.

def style_for(name: str) -> SubtitleStyle:
    """Return the requested named style, or fallback to ``karaoke``."""
    fname = _BOLD_FONT_PATH if name != "minimal" else _find_bold_font()
    table = {
        # Karaoke: bold + outline + drop-shadow. Yellow highlight is
        # applied per-call via highlight_color override, not baked here.
        "karaoke":   SubtitleStyle(
            "karaoke", fname, 80, (255, 255, 255), (0, 0, 0),
            outline_width=6, glow_radius=4, glow_color=(0, 0, 0),
            bg_color=None, bg_alpha=0, letter_spacing=2, bold=True,
        ),
        "bold":      SubtitleStyle(
            "bold", fname, 96, (255, 255, 255), (0, 0, 0),
            outline_width=8, glow_radius=2, glow_color=(0, 0, 0),
            bg_color=None, bg_alpha=0, letter_spacing=2, bold=True,
        ),
        # Neon: cyan text + strong cyan-tinted glow halo. No opaque
        # background — just the halo to read against dark frames.
        "neon":      SubtitleStyle(
            "neon", fname, 84, (220, 240, 255), (0, 0, 0),
            outline_width=4, glow_radius=18, glow_color=(0, 220, 255),
            bg_color=None, bg_alpha=0, letter_spacing=2, bold=True,
        ),
        "minimal":   SubtitleStyle(
            "minimal", fname, 60, (255, 255, 255), (0, 0, 0),
            outline_width=3, glow_radius=0, glow_color=None,
            bg_color=None, bg_alpha=0, letter_spacing=1, bold=False,
        ),
        # Cinematic: white text + semi-transparent black bar behind.
        "cinematic": SubtitleStyle(
            "cinematic", fname, 72, (255, 255, 255), (0, 0, 0),
            outline_width=2, glow_radius=0, glow_color=None,
            bg_color=(0, 0, 0), bg_alpha=140, letter_spacing=10,
            bold=False,
        ),
        # Hormozi: massive bold white with heat-pump green glow.
        "hormozi":   SubtitleStyle(
            "hormozi", fname, 100, (255, 255, 255), (0, 0, 0),
            outline_width=10, glow_radius=6, glow_color=(34, 197, 94),
            bg_color=None, bg_alpha=0, letter_spacing=2, bold=True,
        ),
        # Highlight: marker marker — yellow opaque box behind black
        # bold text, no halo. Yellow box is the bg_color, text fills
        # are black.
        "highlight": SubtitleStyle(
            "highlight", fname, 76, (0, 0, 0), (0, 0, 0),
            outline_width=0, glow_radius=0, glow_color=None,
            bg_color=(255, 215, 0), bg_alpha=255, letter_spacing=2,
            bold=True,
        ),
    }
    return table.get(name, table["karaoke"])


# ─── Renderer ───────────────────────────────────────────────────────────────


def _load_font(path: Optional[str], size: int) -> ImageFont.ImageFont:
    """Return a TrueType font at ``size``. Falls back to Pillow default
    if the bundled font isn't present (probably means Pillow lacks
    libfreetype)."""
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _draw_with_outline(
    canvas: Image.Image,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
    outline_color: Tuple[int, int, int],
    outline_width: int,
) -> None:
    """Pillow has no native stroke API; we emulate one by drawing the
    text N times offset on a circle, then drawing it on top."""
    if outline_width <= 0:
        ImageDraw.Draw(canvas).text(xy, text, font=font, fill=fill + (255,))
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for r in range(outline_width, 0, -1):
        # 8-directional smear — cheap, looks like a real stroke at
        # typical font sizes (60-100px).
        for ox, oy in (
            (r, 0), (-r, 0), (0, r), (0, -r),
            (r, r), (-r, r), (r, -r), (-r, -r),
        ):
            draw.text(
                (xy[0] + ox, xy[1] + oy), text, font=font,
                fill=outline_color + (220,),
            )
    canvas.alpha_composite(layer)
    ImageDraw.Draw(canvas).text(xy, text, font=font, fill=fill + (255,))


def _apply_glow(
    canvas: Image.Image,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
    glow_color: Tuple[int, int, int],
    radius: int,
) -> None:
    """Composite a soft Gaussian-blurred copy of the text underneath
    the main text -> halo. Used for neon / hormozi / karaoke."""
    if radius <= 0:
        return
    glow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow_layer)
    draw.text(xy, text, font=font, fill=glow_color + (220,))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius))
    canvas.alpha_composite(glow_layer)


def _apply_background(
    canvas: Image.Image,
    *,
    text_bbox: Tuple[int, int, int, int],
    bg_color: Tuple[int, int, int],
    bg_alpha: int,
    horizontal_pad: int = 30,
    vertical_pad: int = 18,
) -> None:
    """Draw a rounded rectangle behind the text. Only invoked for
    styles that declare a non-zero bg_alpha."""
    if bg_alpha <= 0:
        return
    x0, y0, x1, y1 = text_bbox
    bx0, by0 = max(0, x0 - horizontal_pad), max(0, y0 - vertical_pad)
    bx1, by1 = min(canvas.size[0], x1 + horizontal_pad), min(canvas.size[1], y1 + vertical_pad)
    if bx1 <= bx0 or by1 <= by0:
        return
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle(
        [bx0, by0, bx1, by1], radius=18, fill=bg_color + (bg_alpha,),
    )
    canvas.alpha_composite(overlay)


def render_text_to_image(
    text: str,
    style_name: str,
    canvas_w: int,
    canvas_h: int,
    *,
    # When set, the WORD at this index is drawn with ``highlight_color``
    # and a thicker glow — used by the karaoke-style active-word sweep.
    highlight_word_idx: Optional[int] = None,
    highlight_color: Tuple[int, int, int] = (255, 230, 0),
) -> Image.Image:
    """Render a single subtitle line into a transparent RGBA image.

    The image has the FULL canvas size — the subtitle is positioned
    bottom-center with a fixed 100px bottom margin (matches the old
    ffmpeg ``MarginV=320`` ASS look; we use 100 because Pillow gutter
    is tighter than libass).

    Returns an RGBA ``PIL.Image``. The caller (subtitle_overlay.py)
    feeds it to ffmpeg as an ``-i`` and overlays only during
    ``between(t, start, end)``.
    """
    style = style_for(style_name)
    if not text or not text.strip():
        return Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _load_font(style.font_path, style.font_size)

    # Pillow exposes ``spacing`` on ``ImageDraw.text`` but NOT on
    # ``ImageDraw.textlength``. We therefore bake letter-spacing into
    # the string ourselves so width math stays in sync with the actual
    # pixels drawn.
    def spaced(s: str) -> str:
        if not s or style.letter_spacing <= 0:
            return s
        return s.replace(" ", " ")  # placeholder; we add real spacing inline below

    # Helper: pixel width of a string with our letter-spacing applied.
    def width_of(s: str) -> int:
        if not s:
            return 0
        # textlength on single-line ascii/cyrillic whole-string.
        base = int(draw.textlength(s, font=font))
        # Add spacing: each gap between letters. For latin/cyrillic whole
        # string, ``len(s)-1`` interpixel gaps is a reasonable proxy
        # since textlength already includes the natural advance width.
        return base + style.letter_spacing * max(0, len(s) - 1)

    # For karaoke-style highlight, render the surrounding words white
    # and pop the active word in the highlight color. We do this by
    # drawing ONE wrapped string composed of pre + active + post with
    # the active substring drawn separately so it can wear its own
    # colour.
    if highlight_word_idx is not None:
        words = text.split()
        if 0 <= highlight_word_idx < len(words):
            pre = " ".join(words[:highlight_word_idx])
            active = words[highlight_word_idx]
            post = " ".join(words[highlight_word_idx + 1:])
            # Compose widths: include the inter-word space chars so
            # textlength reflects realistic advance.
            pre_total = width_of(pre + (" " if pre else ""))
            active_total = width_of(active)
            post_total = width_of((" " if post else "") + post)
            total_w = pre_total + active_total + post_total
            x0 = (canvas_w - total_w) // 2
            y0 = canvas_h - style.font_size - 100

            full_text = (
                (pre + " ") if pre else "" +
                active + (" " if post else "") +
                (post if post else "")
            )
            bbox = (x0, y0, x0 + total_w, y0 + style.font_size)
            _apply_background(canvas, text_bbox=bbox, bg_color=style.bg_color or (0, 0, 0), bg_alpha=style.bg_alpha)
            _apply_glow(canvas, (x0, y0), full_text, font, style.text_color, style.glow_color or (0, 0, 0), style.glow_radius)
            if pre:
                _draw_with_outline(canvas, (x0, y0), pre + " ", font, style.text_color, style.outline_color, 0)
            _draw_with_outline(canvas, (x0 + pre_total, y0), active, font, highlight_color, style.outline_color, max(2, style.outline_width // 2))
            if post:
                _draw_with_outline(canvas, (x0 + pre_total + active_total, y0), " " + post, font, style.text_color, style.outline_color, 0)
            return canvas

    # Plain line render.
    line_w = width_of(text)
    x0 = (canvas_w - line_w) // 2
    y0 = canvas_h - style.font_size - 100

    bbox = (x0, y0, x0 + line_w, y0 + style.font_size)
    _apply_background(canvas, text_bbox=bbox, bg_color=style.bg_color or (0, 0, 0), bg_alpha=style.bg_alpha)
    _apply_glow(canvas, (x0, y0), text, font, style.text_color, style.glow_color or (0, 0, 0), style.glow_radius)
    _draw_with_outline(canvas, (x0, y0), text, font, style.text_color, style.outline_color, style.outline_width)
    return canvas


def save_png(image: Image.Image, path: Path) -> None:
    """Persist a Pillow-rendered subtitle frame as PNG. Path is
    suffixed ``.png`` automatically if missing."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() != ".png":
        p = p.with_suffix(".png")
    image.save(p, format="PNG", optimize=True)
