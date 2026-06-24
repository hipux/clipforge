"""Unit tests for the pure/deterministic helpers in each detection stage.

These cover the heuristic scoring + formatting logic that does NOT need a GPU,
a model, or a real video file. Heavy native deps are stubbed in conftest.py.
"""
import pytest


# ===========================================================================
# Stage: Speech scoring (services/speech_scorer.py)
# ===========================================================================
ss = pytest.importorskip("backend.services.speech_scorer")


class TestTextHeuristics:
    def test_count_questions(self):
        assert ss.count_questions("Really? Are you sure? Yes.") == 2
        assert ss.count_questions("No questions here.") == 0

    def test_count_exclamations(self):
        assert ss.count_exclamations("Wow! Amazing! Stop.") == 2
        assert ss.count_exclamations("calm sentence.") == 0

    def test_count_emotion_keywords_detects_known_word(self):
        # 'shocking' and 'secret' are in EMOTION_KEYWORDS
        assert ss.count_emotion_keywords("This shocking secret will surprise you") >= 2

    def test_count_emotion_keywords_case_insensitive(self):
        assert ss.count_emotion_keywords("SHOCKING") >= 1

    def test_count_emotion_keywords_none(self):
        assert ss.count_emotion_keywords("the cat sat on the mat") == 0


class TestSpeechRate:
    def test_words_per_second(self):
        # 6 words over 4 seconds -> 1.5 words/sec
        seg = {"text": "one two three four five six", "start": 0.0, "end": 4.0}
        assert ss.calculate_speech_rate(seg) == pytest.approx(1.5)

    def test_zero_duration_is_safe(self):
        seg = {"text": "hello world", "start": 2.0, "end": 2.0}
        assert ss.calculate_speech_rate(seg) == 0.0

    def test_negative_duration_is_safe(self):
        seg = {"text": "hello world", "start": 5.0, "end": 1.0}
        assert ss.calculate_speech_rate(seg) == 0.0


class TestSrtTimestamp:
    @pytest.mark.parametrize("seconds,expected", [
        (0.0, "00:00:00,000"),
        (1.5, "00:00:01,500"),
        (61.25, "00:01:01,250"),
        (3661.0, "01:01:01,000"),
    ])
    def test_format_srt_time(self, seconds, expected):
        assert ss.format_srt_time(seconds) == expected

    def test_format_srt_time_negative_clamped(self):
        assert ss.format_srt_time(-5.0) == "00:00:00,000"


class TestScoreSegment:
    def test_returns_score_0_to_100(self):
        seg = {"text": "This shocking secret! Are you ready?", "start": 0.0, "end": 3.0}
        score = ss.score_segment(seg)
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 100.0

    def test_engaging_scores_higher_than_dull(self):
        engaging = {"text": "Shocking secret revealed! Are you ready? Wow!",
                    "start": 0.0, "end": 3.0}
        dull = {"text": "um so yeah the the thing", "start": 0.0, "end": 3.0}
        assert ss.score_segment(engaging) > ss.score_segment(dull)

    def test_dull_segment_scores_zero(self):
        dull = {"text": "the cat sat on the mat", "start": 0.0, "end": 6.0}
        assert ss.score_segment(dull) == 0.0


class TestSubtitleStyle:
    def test_known_style_returns_definition(self):
        assert ss.get_subtitle_style_definition("neon").startswith("Style:")

    def test_unknown_style_falls_back_to_karaoke(self):
        assert ss.get_subtitle_style_definition("does-not-exist") == \
            ss.get_subtitle_style_definition("karaoke")


# ===========================================================================
# Stage: Scene detection scoring (services/scene_detector.py)
# ===========================================================================
sd = pytest.importorskip("backend.services.scene_detector")


class TestSceneScoring:
    def test_score_audio_energy_empty_returns_zero(self):
        import numpy as np
        assert sd.score_audio_energy(np.array([]), np.array([]), 0.0, 5.0) == 0.0

    def test_score_audio_energy_in_range(self):
        import numpy as np
        energy = np.array([0.1, 0.2, 0.9, 0.95, 0.15])
        times = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        s = sd.score_audio_energy(energy, times, 2.0, 3.0)
        assert isinstance(s, float)
        assert 0.0 <= s <= 100.0

    def test_score_audio_energy_loud_window_beats_quiet(self):
        import numpy as np
        energy = np.array([0.1, 0.1, 0.9, 0.95, 0.1, 0.1])
        times = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        loud = sd.score_audio_energy(energy, times, 2.0, 3.0)
        quiet = sd.score_audio_energy(energy, times, 4.0, 5.0)
        assert loud > quiet

    def test_score_scene_density_empty_returns_zero(self):
        assert sd.score_scene_density([], 0.0, 10.0) == 0.0

    def test_score_scene_density_in_range(self):
        changes = [1.0, 3.0, 5.0, 7.0]
        s = sd.score_scene_density(changes, 0.0, 10.0)
        assert isinstance(s, float)
        assert 0.0 <= s <= 100.0

    def test_score_scene_density_denser_scores_higher(self):
        sparse = sd.score_scene_density([1.0], 0.0, 60.0)
        dense = sd.score_scene_density([1, 2, 3, 4, 5, 6, 7, 8], 0.0, 60.0)
        assert dense > sparse


# ===========================================================================
# Stage: LLM director text cleanup (services/llm_director.py)
# ===========================================================================
ld = pytest.importorskip("backend.services.llm_director")


class TestStripThink:
    def test_removes_think_block(self):
        raw = "<think>internal reasoning</think>{\"moments\": []}"
        out = ld._strip_think(raw)
        assert "<think>" not in out and "internal reasoning" not in out
        assert "moments" in out

    def test_passthrough_without_think(self):
        raw = '{"moments": []}'
        assert ld._strip_think(raw).strip() == raw