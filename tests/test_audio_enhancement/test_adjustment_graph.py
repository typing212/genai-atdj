"""Tests for atdj/audio/adjustment_graph.py.

Pure logic tests run without an LLM.
Integration tests (require LLM + API key) are marked with @pytest.mark.integration.
"""
import pytest

from atdj.audio.adjustment_graph import (
    apply_constraint,
    compute_intent_overrides,
    resolve_targets,
    DEFAULT_PARAMS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_playlist():
    return [
        {"type": "song",    "title": "A", "orchestra": "Orq A", "style": "TANGO",   "tanda_id": 0},
        {"type": "song",    "title": "B", "orchestra": "Orq A", "style": "TANGO",   "tanda_id": 0},
        {"type": "cortina", "title": "Cortina 1"},
        {"type": "song",    "title": "C", "orchestra": "Di Sarli", "style": "TANGO",  "tanda_id": 1},
        {"type": "song",    "title": "D", "orchestra": "Di Sarli", "style": "TANGO",  "tanda_id": 1},
        {"type": "cortina", "title": "Cortina 2"},
        {"type": "song",    "title": "E", "orchestra": "Orq B", "style": "VALS",    "tanda_id": 2},
        {"type": "song",    "title": "F", "orchestra": "Orq B", "style": "VALS",    "tanda_id": 2},
    ]


# ── apply_constraint ──────────────────────────────────────────────────────────

class TestApplyConstraint:
    def test_up_floor_track_already_higher(self):
        # ref=-16, delta=1.5 → target=-14.5 — track auto=-14.0 (already higher) → unchanged
        result = apply_constraint("up", -16.0, 1.5, -14.0)
        assert result == -14.0

    def test_up_floor_track_lower_than_target(self):
        # ref=-16, delta=1.5 → target=-14.5 — track auto=-17.0 → raised to -14.5
        result = apply_constraint("up", -16.0, 1.5, -17.0)
        assert result == pytest.approx(-14.5)

    def test_up_floor_track_exactly_at_target(self):
        result = apply_constraint("up", -16.0, 1.5, -14.5)
        assert result == pytest.approx(-14.5)

    def test_down_ceiling_track_already_lower(self):
        # ref=-12, delta=3.0 → target=-15.0 — track auto=-16.0 (already lower) → unchanged
        result = apply_constraint("down", -12.0, 3.0, -16.0)
        assert result == -16.0

    def test_down_ceiling_track_higher_than_target(self):
        # ref=-12, delta=3.0 → target=-15.0 — track auto=-11.0 → lowered to -15.0
        result = apply_constraint("down", -12.0, 3.0, -11.0)
        assert result == pytest.approx(-15.0)

    def test_reset_returns_auto_value(self):
        result = apply_constraint("reset", -14.0, 0.0, -17.5)
        assert result == -17.5

    def test_up_eq_gain_floor(self):
        # bass: ref=1.5, delta=0.5 → target=2.0 — track auto=2.5 (already higher) → unchanged
        result = apply_constraint("up", 1.5, 0.5, 2.5)
        assert result == 2.5

    def test_down_eq_gain_ceiling(self):
        # presence: ref=1.5, delta=0.5 → target=1.0 — track auto=0.8 (already lower) → unchanged
        result = apply_constraint("down", 1.5, 0.5, 0.8)
        assert result == 0.8

    def test_down_eq_gain_ceiling_applied(self):
        # presence: ref=1.5, delta=0.5 → target=1.0 — track auto=2.0 → lowered to 1.0
        result = apply_constraint("down", 1.5, 0.5, 2.0)
        assert result == pytest.approx(1.0)


# ── resolve_targets ───────────────────────────────────────────────────────────

class TestResolveTargets:
    def test_rest_returns_all_songs_after_current(self, simple_playlist):
        # current=1 (B), rest = C(3), D(4), E(6), F(7)
        result = resolve_targets("rest", simple_playlist, 1, None)
        assert result == [3, 4, 6, 7]

    def test_rest_skips_cortinas(self, simple_playlist):
        result = resolve_targets("rest", simple_playlist, 1, None)
        for i in result:
            assert simple_playlist[i]["type"] == "song"

    def test_next_song_skips_cortina(self, simple_playlist):
        # current=1 (B), cortina at 2, next song is C at 3
        result = resolve_targets("next_song", simple_playlist, 1, None)
        assert result == [3]

    def test_next_song_no_skip_needed(self, simple_playlist):
        # current=0 (A), next song is B at 1
        result = resolve_targets("next_song", simple_playlist, 0, None)
        assert result == [1]

    def test_next_tanda(self, simple_playlist):
        # current=1 (B, tanda_id=0), next tanda is tanda_id=1 → C(3), D(4)
        result = resolve_targets("next_tanda", simple_playlist, 1, None)
        assert result == [3, 4]

    def test_next_tanda_from_second_tanda(self, simple_playlist):
        # current=3 (C, tanda_id=1), next tanda is tanda_id=2 → E(6), F(7)
        result = resolve_targets("next_tanda", simple_playlist, 3, None)
        assert result == [6, 7]

    def test_next_tanda_no_more_tandas(self, simple_playlist):
        # current=6 (E, tanda_id=2), no more tandas after
        result = resolve_targets("next_tanda", simple_playlist, 6, None)
        assert result == []

    def test_specific_by_orchestra(self, simple_playlist):
        # "di sarli" matches orchestra of C(3) and D(4)
        result = resolve_targets("specific", simple_playlist, 0, "di sarli")
        assert result == [3, 4]

    def test_specific_by_style(self, simple_playlist):
        # "vals" matches style of E(6) and F(7)
        result = resolve_targets("specific", simple_playlist, 0, "vals")
        assert result == [6, 7]

    def test_specific_case_insensitive(self, simple_playlist):
        result = resolve_targets("specific", simple_playlist, 0, "DI SARLI")
        assert result == [3, 4]

    def test_specific_no_match_returns_empty(self, simple_playlist):
        result = resolve_targets("specific", simple_playlist, 0, "nonexistent")
        assert result == []

    def test_no_songs_after_last_track(self, simple_playlist):
        # current=7 (last), nothing after
        result = resolve_targets("rest", simple_playlist, 7, None)
        assert result == []

    def test_rest_from_beginning(self, simple_playlist):
        # current=0 (A), rest = B(1), C(3), D(4), E(6), F(7)
        result = resolve_targets("rest", simple_playlist, 0, None)
        assert result == [1, 3, 4, 6, 7]


# ── compute_intent_overrides ──────────────────────────────────────────────────

class TestComputeIntentOverrides:
    def test_loudness_up_small_uses_default_reference(self):
        # DEFAULT target_lufs = -14.0, small delta = 1.5 → target = -12.5
        intent = {"feature": "loudness", "direction": "up", "magnitude": "small"}
        overrides = compute_intent_overrides(intent, 3)
        assert len(overrides) == 3
        for o in overrides:
            assert o.get("target_lufs") == pytest.approx(-12.5)

    def test_loudness_down_medium(self):
        # DEFAULT target_lufs = -14.0, medium delta = 3.0 → target = -17.0
        intent = {"feature": "loudness", "direction": "down", "magnitude": "medium"}
        overrides = compute_intent_overrides(intent, 2)
        for o in overrides:
            assert o.get("target_lufs") == pytest.approx(-17.0)

    def test_bass_up_large(self):
        # DEFAULT eq_low_gain = 2.0, large delta = 2.0 → target = 4.0
        intent = {"feature": "bass", "direction": "up", "magnitude": "large"}
        overrides = compute_intent_overrides(intent, 4)
        for o in overrides:
            assert o.get("eq_low_gain") == pytest.approx(4.0)

    def test_reset_returns_empty_overrides(self):
        intent = {"feature": "loudness", "direction": "reset", "magnitude": "small"}
        overrides = compute_intent_overrides(intent, 3)
        for o in overrides:
            assert o == {}

    def test_unknown_feature_returns_empty(self):
        intent = {"feature": "unknown_feature", "direction": "up", "magnitude": "small"}
        overrides = compute_intent_overrides(intent, 2)
        for o in overrides:
            assert o == {}

    def test_track_count_respected(self):
        intent = {"feature": "presence", "direction": "down", "magnitude": "small"}
        overrides = compute_intent_overrides(intent, 5)
        assert len(overrides) == 5

    def test_zero_tracks(self):
        intent = {"feature": "loudness", "direction": "up", "magnitude": "small"}
        overrides = compute_intent_overrides(intent, 0)
        assert overrides == []


# ── Integration tests (require LLM) ──────────────────────────────────────────

@pytest.mark.integration
class TestParseRequestIntegration:
    """These tests call the real LLM and require GEMINI_API_KEY (or legacy GOOGLE_API_KEY) to be set."""

    def _run_parse(self, message: str, playlist=None, current_index=0) -> dict:
        from atdj.audio.adjustment_graph import build_adjustment_graph, DEFAULT_PARAMS

        if playlist is None:
            playlist = [
                {"type": "song", "title": "El Retirado", "orchestra": "Di Sarli",
                 "style": "TANGO", "tanda_id": 0},
                {"type": "song", "title": "La Cumparsita", "orchestra": "D'Arienzo",
                 "style": "TANGO", "tanda_id": 1},
            ]

        initial = {
            "user_message": message,
            "playlist": playlist,
            "current_index": current_index,
            "auto_enhance_on": True,
            "output_dir": "/tmp",
            "resolved_paths": {},
            "scope": None, "feature": None, "direction": None,
            "magnitude": None, "target_name": None,
            "needs_clarification": False,
            "clarification_question": "",
            "clarification_options": [],
            "rejected": False,
            "rejection_options": [],
            "target_indices": [],
            "reference_params": None,
            "computed_overrides": [],
            "execution_results": [],
            "store_intent": False,
            "intent_to_store": None,
            "reply": "",
            "activity_log": [],
        }
        graph = build_adjustment_graph()
        from atdj.audio.adjustment_graph import parse_request
        return parse_request(initial)

    def test_bass_down_small(self):
        result = self._run_parse("turn down the bass a little")
        assert result.get("feature") == "bass"
        assert result.get("direction") == "down"
        assert result.get("magnitude") == "small"
        assert result.get("needs_clarification") is False

    def test_loudness_up_medium(self):
        result = self._run_parse("the music is too quiet, make it louder")
        assert result.get("feature") == "loudness"
        assert result.get("direction") == "up"

    def test_current_song_scope(self):
        result = self._run_parse("this song is too harsh")
        assert result.get("scope") == "current"

    def test_rest_scope(self):
        result = self._run_parse("everything after this is too noisy")
        assert result.get("scope") == "rest"
        assert result.get("feature") == "noise"

    def test_reset_direction(self):
        result = self._run_parse("go back to default")
        assert result.get("direction") == "reset"

    def test_use_original(self):
        result = self._run_parse("use original for the next tanda")
        assert result.get("direction") == "reset"

    def test_named_target_orchestra(self):
        result = self._run_parse("more presence in the Di Sarli tanda")
        assert result.get("scope") == "specific"
        assert result.get("target_name") is not None
        assert "sarli" in result["target_name"].lower()
        assert result.get("feature") == "presence"
        assert result.get("direction") == "up"

    def test_ambiguous_triggers_clarification(self):
        result = self._run_parse("it sounds a bit off")
        assert result.get("needs_clarification") is True
        assert result.get("clarification_question")
