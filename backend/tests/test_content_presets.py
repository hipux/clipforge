"""Tests for content presets — locked-shape contract + apply_to_prompt."""
import pytest

from backend.services.content_presets import (
    ContentPreset, PRESETS, get_preset, list_presets, apply_to_prompt,
)
from backend.services.context_builder import build_system_prompt


# ===== Safe getters =====

def test_get_preset_returns_known():
    p = get_preset("films_anime")
    assert p.id == "films_anime"


def test_get_preset_unknown_falls_back_default():
    assert get_preset("does_not_exist").id == "default"


def test_get_preset_empty_string_falls_back_default():
    assert get_preset("").id == "default"


def test_list_presets_has_default_first():
    presets = list_presets()
    assert presets[0].id == "default"
    assert len(presets) == len(PRESETS)


# ===== Schema =====

def test_every_preset_min_le_max():
    """min_duration < max_duration; otherwise moment generation chokes."""
    for preset in PRESETS.values():
        assert preset.min_duration < preset.max_duration, (
            f"{preset.id}: min={preset.min_duration} max={preset.max_duration}"
        )


def test_every_preset_has_at_least_one_content_type():
    for preset in PRESETS.values():
        assert preset.content_types, (
            f"{preset.id}: content_types is empty"
        )


def test_every_preset_has_nonempty_icon():
    """Every preset has a lucide-react icon name so the dashboard renders
    a single cohesive icon system (no unicode glyph mixing)."""
    for preset in PRESETS.values():
        assert preset.icon.strip(), f"{preset.id}: missing icon"


def test_preset_dataclass_is_frozen():
    p = get_preset("streams")
    with pytest.raises(Exception):  # FrozenInstanceError subclass of AttributeError
        p.id = "hacked"  # type: ignore[misc]


def test_preset_weights_keys_are_known_signals():
    """Only weights that the LLM actually scores survive this filter (UI sanity)."""
    valid = {"hook_strength", "self_contained", "audio_energy", "scene_density"}
    for preset in PRESETS.values():
        unknown = set(preset.weights) - valid
        assert not unknown, f"{preset.id}: unknown weights: {unknown}"


# ===== apply_to_prompt =====

def test_apply_to_prompt_default_is_noop():
    prompt = build_system_prompt(30, 90, 15)
    p = get_preset("default")
    out = apply_to_prompt(prompt, p)
    # Default preset must be byte-identical so pre-preset runs don't shift.
    assert out == prompt


def test_apply_to_prompt_films_anime_injects_instructions():
    prompt = build_system_prompt(30, 90, 15)
    p = get_preset("films_anime")
    out = apply_to_prompt(prompt, p)
    assert "CONTENT TYPE: Film / Anime" in out
    assert "YamNet music" in out  # preset-specific rule
    # Schema anchor is still there — preset never breaks the JSON contract.
    assert "Return ONLY valid JSON matching this exact schema" in out


def test_apply_to_prompt_streams_injects_instructions():
    prompt = build_system_prompt(30, 90, 15)
    p = get_preset("streams")
    out = apply_to_prompt(prompt, p)
    assert "CONTENT TYPE: Stream" in out
    assert "YamNet audio events" in out


def test_apply_to_prompt_youtube_cuts_injects_instructions():
    prompt = build_system_prompt(30, 90, 15)
    p = get_preset("youtube_cuts")
    out = apply_to_prompt(prompt, p)
    assert "CONTENT TYPE: YouTube-style cuts" in out


def test_apply_to_prompt_anchor_uniqueness():
    """apply_to_prompt must NOT destroy the schema anchor (LLM depends on it)."""
    prompt = build_system_prompt(30, 90, 15)
    for preset_id in ("films_anime", "streams", "youtube_cuts", "default"):
        out = apply_to_prompt(prompt, get_preset(preset_id))
        assert out.count("Return ONLY valid JSON matching this exact schema") == 1, (
            f"preset {preset_id} duplicated or removed the JSON schema anchor"
        )


def test_apply_to_prompt_injects_before_schema_anchor():
    """Preset section must appear BEFORE the JSON block — helps LLM parse order."""
    prompt = build_system_prompt(30, 90, 15)
    out = apply_to_prompt(prompt, get_preset("films_anime"))
    pos_marker = out.find("CONTENT TYPE: Film / Anime")
    pos_schema = out.find("Return ONLY valid JSON matching this exact schema")
    assert pos_marker < pos_schema


def test_apply_to_prompt_user_instructions_still_appended():
    """USER INSTRUCTIONS block is preserved when a non-default preset is applied."""
    prompt = build_system_prompt(30, 90, 15, user_instructions="выбери только панчей")
    out = apply_to_prompt(prompt, get_preset("films_anime"))
    assert "USER INSTRUCTIONS" in out
    assert "панчей" in out
