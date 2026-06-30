"""Verify ProcessedClip round-trips score_breakdown correctly.

We caught a Pydantic forward-ref bug at import time (ScoreBreakdown declared
below ProcessedClip) — these tests pin the contract so a future refactor
can't break it silently.
"""
import pytest
from backend.models import ProcessedClip, ScoreBreakdown


def _effects():
    return {"subtitles": False, "blur_background": False,
            "mirror": False, "color_correction": False,
            "subtitle_style": "karaoke", "banner": None}


def test_processed_clip_score_optional():
    pc = ProcessedClip(id='1', moment_id='m1', file_path='x.mp4',
                       status='completed', effects=_effects(),
                       score=None)
    assert pc.score is None
    assert pc.model_dump()["score"] is None


def test_processed_clip_with_score():
    pc = ProcessedClip(
        id='1', moment_id='m1', file_path='x.mp4', status='completed',
        effects=_effects(),
        score=ScoreBreakdown(overall=82, hook=0.75, self_contained=0.6,
                             pacing=0.4, content_type='hook', content_icon='Zap',
                             reason='Clear question with payoff.',
                             speakers=['Person A']),
    )
    assert pc.score.overall == 82
    assert pc.score.content_icon == 'Zap'
    assert pc.score.speakers == ['Person A']
    # Round-trip through JSON — this is what hits the API.
    data = pc.model_dump()
    assert data['score']['content_type'] == 'hook'
    assert data['score']['content_icon'] == 'Zap'
    assert data['score']['speakers'] == ['Person A']


def test_processed_clip_without_score_arg_defaults_to_none():
    pc = ProcessedClip(id='1', moment_id='m1', file_path='x.mp4',
                       status='completed', effects=_effects())
    assert pc.score is None


def test_processed_clip_legacy_clip_serializes_with_null_score():
    """Real-world: legacy clip row has no score_json → score=None serialized."""
    pc = ProcessedClip(id='legacy', moment_id='m1', file_path='x.mp4',
                       status='completed', effects=_effects(), score=None)
    payload = pc.model_dump(mode='json')
    assert payload["score"] is None
