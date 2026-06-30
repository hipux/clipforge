"""Build ScoreBreakdown from a detected moment.

Single small helper so the Publish UI can render "why this clip" without
re-doing math. Pure functions only — no DB, no ffmpeg, easy to unit-test.
"""
from __future__ import annotations

from typing import Iterable, List, Optional


# Lucide icon name per content type. The frontend renders these via
# `lucide-react`'s dynamic import (`<DynamicIcon name="..."/>`-style).
# We deliberately do NOT use unicode emoji here — the operator dashboard
# uses custom SVG icons so icon weight, color, and hover/tooltip match
# the rest of the design system.
CONTENT_TYPE_ICON = {
    "hook":        "Zap",        # attention-grabber
    "explanation": "Lightbulb",  # information-dense talking
    "funny":       "Smile",      # comedic beat
    "story":       "BookOpen",   # narrative arc
    "action":      "Flame",      # fight / chase / sports
    "music":       "Music",      # song or dance
    "reaction":    "Heart",      # shock / awe
    "emotional":   "HeartHandshake",  # emotional beat
    "anime":       "Sparkles",   # anime-specific for content-preset (#4)
    "stream":      "Gamepad2",   # stream clip specific
}
_DEFAULT_ICON = "Clapperboard"


def icon_for(content_type: str) -> str:
    """Return a lucide icon name for `content_type`. Falls back to Clapperboard."""
    return CONTENT_TYPE_ICON.get((content_type or "").lower(), _DEFAULT_ICON)


def _avg(values: Iterable[float]) -> float:
    seq = [v for v in values if v is not None]
    return (sum(seq) / len(seq)) if seq else 0.0


def build_score_breakdown(
    virality_score: Optional[float] = None,
    hook_strength: Optional[float] = None,
    self_contained: Optional[float] = None,
    content_type: Optional[str] = "",
    reasoning: Optional[str] = "",
    speakers: Optional[List[str]] = None,
    yamnet_energy: Optional[float] = None,
) -> dict:
    """Pack a Publish-UI ScoreBreakdown dict.

    Inputs are 0-1 normalized (virality_score is 0-100). Output dict keys
    match `backend.models.ScoreBreakdown` exactly so we can `**dict` into it
    without renaming.
    """
    speakers = speakers or []
    overall = int(round(virality_score or 0))
    # Pacing = YamNet audio energy on 0-1; falls back to hook_strength so the
    # breakdown card always renders three bars. We just visualize the numbers
    # — no special weighting here, the operator reads them as-is.
    pacing = yamnet_energy if yamnet_energy is not None else _avg([hook_strength])
    return {
        "overall":       max(0, min(100, overall)),
        "hook":          round(_avg([hook_strength]), 2),
        "self_contained": round(_avg([self_contained]), 2),
        "pacing":        round(pacing, 2),
        "content_type":  (content_type or "").strip(),
        "content_icon":  icon_for(content_type or ""),
        "reason":        (reasoning or "").strip(),
        "speakers":      [s for s in speakers if s],
    }

