"""Tests for score_breakdown helper (publish-UI "why this clip")."""
import pytest
from backend.services.score_breakdown import (
    build_score_breakdown, emoji_for, CONTENT_TYPE_EMOJI,
)


def test_emoji_for_known_content_types():
    for ct in ("hook", "explanation", "funny", "story",
               "action", "music", "reaction", "emotional", "anime", "stream"):
        assert emoji_for(ct) == CONTENT_TYPE_EMOJI[ct]


def test_emoji_for_unknown_returns_default():
    assert emoji_for("") == "🎬"
    assert emoji_for(None) == "🎬"  # type: ignore[arg-type]
    assert emoji_for("totally_made_up") == "🎬"
    assert emoji_for("HOOK") == CONTENT_TYPE_EMOJI["hook"]  # case-insensitive


def test_build_score_breakdown_full():
    out = build_score_breakdown(
        virality_score=87.4,
        hook_strength=0.92,
        self_contained=0.71,
        content_type="hook",
        reasoning="Strong question hook + clear payoff.",
        speakers=["Person A"],
        yamnet_energy=0.45,
    )
    assert out["overall"] == 87          # rounded
    assert out["hook"] == 0.92
    assert out["self_contained"] == 0.71
    assert out["pacing"] == 0.45         # yamnet_energy wins over hook fallback
    assert out["content_type"] == "hook"
    assert out["content_emoji"] == "🎣"
    assert "hook" in out["reason"].lower()
    assert out["speakers"] == ["Person A"]


def test_build_score_breakdown_clamp_overall():
    assert build_score_breakdown(virality_score=120.0)["overall"] == 100
    assert build_score_breakdown(virality_score=-5.0)["overall"] == 0


def test_build_score_breakdown_no_inputs_uses_defaults():
    out = build_score_breakdown()  # all None
    assert out == {
        "overall": 0,
        "hook": 0.0,
        "self_contained": 0.0,
        "pacing": 0.0,                 # both hook and yamnet are None → 0.0
        "content_type": "",
        "content_emoji": "🎬",          # default fallback
        "reason": "",
        "speakers": [],
    }


def test_build_score_breakdown_pacing_falls_back_to_hook_when_no_yamnet():
    out = build_score_breakdown(hook_strength=0.7)
    assert out["pacing"] == 0.7


def test_build_score_breakdown_speakers_filtered():
    out = build_score_breakdown(speakers=["Person A", "", None, "Person B"])
    assert out["speakers"] == ["Person A", "Person B"]


def test_emoji_table_is_complete_for_documented_types():
    """content_type values produced by the LLM should all map to something."""
    # These are the values surface in pipeline.JSON. If a new one ships, add
    # it to the table — this test reminder prevents a silent "🎬" fallback.
    required = {"hook", "explanation", "funny", "story",
                "action", "music", "reaction", "emotional"}
    assert required.issubset(CONTENT_TYPE_EMOJI.keys())
