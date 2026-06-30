"""Content presets for the detection pipeline.

Each preset reshapes the LLM system prompt + scoring weights so the
detection logic suits a kind of source video:

  - "youtube_cuts"  — talking-head podcasts, vlogs, essays.
                      hook + self_contained drive virality.
  - "films_anime"   — anime / movie clips.
                      action, music, emotional beats; subtitles off.
  - "streams"       — Twitch / kick / game-stream highlights.
                      short, audio-event-heavy (YamNet laugh/shock).

Adding a preset = adding one frozen dataclass + registering under PRESETS.
No DB, no migrations — the active preset is sent with each request.

Public API:
    PRESETS            — dict id → preset
    get_preset(id)     — safe getter, falls back to 'default'
    list_presets()     — dashboard / UI summary
    apply_to_prompt    — pure helper that augments the system prompt
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ContentPreset:
    """Immutable, JSON-serialisable config for a content family."""
    id: str
    name: str
    description: str
    icon: str                        # lucide-react icon name (no unicode emoji)
    min_duration: int
    max_duration: int
    content_types: List[str]         # LLM is asked to choose among these
    weights: Dict[str, float] = field(default_factory=dict)
    prompt_section: str = ""          # appended to the LLM system prompt
    extra_rules: str = ""             # appended before "Return ONLY valid JSON"


# Each preset defines what the LLM should look for. Defaults behave exactly
# like the pre-preset pipeline so we never silently regress existing runs.
# Icons are lucide-react names (no unicode emoji) so the dashboard uses a
# single coherent icon system instead of mixing unicode glyphs with SVG icons.
PRESETS: Dict[str, ContentPreset] = {
    "default": ContentPreset(
        id="default",
        name="Universal",
        description="General viral clips — hook + self-contained balance.",
        icon="Clapperboard",
        min_duration=30,
        max_duration=90,
        content_types=["reaction", "explanation", "story", "joke", "argument"],
        weights={"hook_strength": 1.0, "self_contained": 1.0, "audio_energy": 0.6,
                 "scene_density": 0.4},
        prompt_section="",
    ),

    "youtube_cuts": ContentPreset(
        id="youtube_cuts",
        name="YouTube cuts",
        description="Talking-head essays, vlogs, podcasts. Long hook + clear payoff.",
        icon="Mic",
        min_duration=30,
        max_duration=80,
        content_types=["explanation", "story", "reaction", "argument", "joke"],
        weights={"hook_strength": 1.2, "self_contained": 1.2, "audio_energy": 0.5},
        prompt_section=(
            "\nCONTENT TYPE: YouTube-style cuts (talking host / essay / podcast).\n"
            "- Clip must open with a CLEAR HOOK in the first 3 seconds:\n"
            "  question, controversial claim, anticipation of payoff, or\n"
            "  visual gag.\n"
            "- Self-contained dominates: a cold viewer has to understand\n"
            "  who is talking and what is going on within ~5 seconds.\n"
            "- Trim aggressively around the punchline so the final seconds\n"
            "  land cleanly.\n"
        ),
    ),

    "films_anime": ContentPreset(
        id="films_anime",
        name="Films / Anime",
        description="Action / emotional / musical beats. NO subtitles overlay.",
        icon="Sparkles",
        min_duration=45,
        max_duration=90,
        content_types=["action", "emotional", "music", "anime"],
        weights={"hook_strength": 1.0, "self_contained": 0.8, "audio_energy": 1.5,
                 "scene_density": 1.3},
        prompt_section=(
            "\nCONTENT TYPE: Film / Anime / animated feature.\n"
            "- There is NO speech to transcribe — pick VISUAL / AUDIO beats.\n"
            "- Prioritise action, emotional, and music scenes. Score audio\n"
            "  energy and scene density heavily (YamNet music / explosions /\n"
            "  dialogue peaks are strong signals).\n"
            "- Subtitles are OFF for this preset (auto-detected from\n"
            "  source). Use ORIGINAL-language title only if speech exists,\n"
            "  otherwise translate the SCENE TITLE to a short Russian hook.\n"
            "- Don't cut on a cliffhanger — the beat itself must feel\n"
            "  complete: action lands, music resolves, emotional arc closes.\n"
        ),
    ),

    "streams": ContentPreset(
        id="streams",
        name="Streams / Gaming",
        description="VODs and stream highlights — laughter, shock, fails, big plays.",
        icon="Gamepad2",
        min_duration=20,
        max_duration=55,
        content_types=["reaction", "funny", "action", "stream"],
        weights={"hook_strength": 0.9, "self_contained": 0.7, "audio_energy": 1.4,
                 "scene_density": 1.1},
        prompt_section=(
            "\nCONTENT TYPE: Stream / gaming VOD.\n"
            "- YamNet audio events (laughter, scream, gasp, gunshots) are\n"
            "  the strongest signal — they almost always mark a clip-worthy\n"
            "  beat.\n"
            "- Short and punchy: 20-55 second range, no slow lulls.\n"
            "- Self-contained only matters for narrative moments (streamer's\n"
            "  explanation / setup before a big play); for pure reaction\n"
            "  fails, the reaction ITSELF is the hook.\n"
            "- Streamer voice may be in any language — translate title to\n"
            "  Russian unless the bit is language-independent (laugh, fail).\n"
        ),
    ),
}


def get_preset(preset_id: str) -> ContentPreset:
    """Get a preset by id; fall back to 'default' on unknown id (never raise)."""
    if not preset_id:
        return PRESETS["default"]
    return PRESETS.get(preset_id, PRESETS["default"])


def list_presets() -> List[ContentPreset]:
    """All presets in deterministic display order (default first)."""
    keys = ["default", "youtube_cuts", "films_anime", "streams"]
    extras = sorted(set(PRESETS.keys()) - set(keys))
    return [PRESETS[k] for k in keys + extras]


def apply_to_prompt(system_prompt: str, preset: ContentPreset) -> str:
    """Insert the preset's prompt_section + extra_rules just BEFORE the schema
    block (the long 'Return ONLY valid JSON matching this exact schema:').
    Default preset is a no-op so existing runs are byte-identical.
    """
    if preset.id == "default" and not preset.prompt_section and not preset.extra_rules:
        return system_prompt
    insertion = ""
    if preset.prompt_section:
        insertion += preset.prompt_section
    if preset.extra_rules:
        insertion += "\n" + preset.extra_rules
    # Find the schema anchor and inject right before it.
    anchor = "Return ONLY valid JSON matching this exact schema"
    if anchor not in system_prompt:
        # Fallback: append — better than dropping the preset.
        return system_prompt + insertion
    return system_prompt.replace(anchor, insertion.strip() + "\n" + anchor)


def preset_to_dict(p: ContentPreset) -> dict:
    """JSON-serialisable shape for the /api/moments/presets endpoint."""
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "icon": p.icon,
        "min_duration": p.min_duration,
        "max_duration": p.max_duration,
        "content_types": p.content_types,
    }
