"""Build ScoreBreakdown from a detected moment.

Single small helper so the Publish UI can render "why this clip" without
re-doing math. Pure functions only — no DB, no ffmpeg, easy to unit-test.
"""
from __future__ import annotations

from typing import Iterable, List, Optional


# Emoji per content type — chosen so the UI can render a single badge without
# shipping a backend enum list. Keep short to fit a 14-px chip.
CONTENT_TYPE_EMOJI = {
    "hook":        "🎣",  # attention-grabber
    "explanation": "🧠",  # information-dense talking
    "funny":       "😂",  # comedic beat
    "story":       "📖",  # narrative arc
    "action":      "⚔️",  # fight / chase / sports
    "music":       "🎶",  # song or dance
    "reaction":    "😱",  # shock / awe
    "emotional":   "💔",  # emotional beat
    "anime":       "🎌",  # anime-specific for content-preset (#4)
    "stream":      "🎮",  # stream clip specific
}
_DEFAULT_EMOJI = "🎬"


def emoji_for(content_type: str) -> str:
    """Return a single emoji for `content_type`. Falls back to 🎬."""
    return CONTENT_TYPE_EMOJI.get((content_type or "").lower(), _DEFAULT_EMOJI)


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
        "content_emoji": emoji_for(content_type or ""),
        "reason":        (reasoning or "").strip(),
        "speakers":      [s for s in speakers if s],
    }
