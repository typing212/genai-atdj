"""Tests for atdj/audio/adjustment_graph.py.

Pure logic tests run without an LLM.
Integration tests (require LLM + API key) are marked with @pytest.mark.integration.
"""
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from atdj.audio.adjustment_graph import (
    apply_constraint,
    compute_adjustments,
    execute_enhancement,
    format_reply,
    measure_reference,
    resolve_targets,
    resolve_targets_node,
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

    def test_format_reply_says_left_unchanged_for_up_direction(self):
        """Mirrors UI 9.3.3 — the 'Tracks that were already louder than the
        target were left unchanged' wording must be in every up-direction reply."""
        state = {
            "execution_results": [{"name": "t1"}, {"name": "t2"}],
            "direction": "up", "feature": "loudness", "magnitude": "small",
            "reply": "",
        }
        out = format_reply(state)
        assert "louder" in out["reply"]
        assert "left unchanged" in out["reply"]

    def test_format_reply_says_left_unchanged_for_down_direction(self):
        state = {
            "execution_results": [{"name": "t1"}],
            "direction": "down", "feature": "presence", "magnitude": "medium",
            "reply": "",
        }
        out = format_reply(state)
        assert "softer" in out["reply"]
        assert "left unchanged" in out["reply"]

    def test_next_tanda_only_returns_immediate_next_not_all_subsequent(self):
        """Regression for the 'next_tanda matched 12 tracks' bug from manual testing.
        With THREE tandas of 4 songs each (12 songs total), asking for `next_tanda`
        from inside tanda 0 must return EXACTLY the 4 songs of tanda 1 — NOT all 8
        songs from tandas 1+2 lumped together. Pre-fix, the page_main PLAN handler
        let multiple stacked plans share tanda_id=0/1/2; this test guards the
        playlist-level resolver behavior assuming clean ids (which the new
        page_main offset + `_renumber_tanda_ids` migration guarantee at runtime)."""
        playlist = []
        for tid in range(3):
            for letter in "ABCD":
                playlist.append({
                    "type": "song", "title": f"T{tid}-{letter}",
                    "orchestra": f"Orq{tid}", "style": "TANGO", "tanda_id": tid,
                })
            if tid < 2:
                playlist.append({"type": "cortina", "title": f"Cortina{tid}"})

        # current = first song of tanda 0 (index 0). next_tanda must be tanda 1.
        result = resolve_targets("next_tanda", playlist, 0, None)
        assert len(result) == 4, (
            f"Expected exactly 4 tracks (one tanda), got {len(result)} — "
            f"resolver is lumping multiple tandas together. Indices: {result}"
        )
        # Indices for tanda 1 are 5..8 (after the 4 songs of tanda 0 + 1 cortina).
        assert result == [5, 6, 7, 8]
        # And every returned track must actually have tanda_id=1.
        assert all(playlist[i]["tanda_id"] == 1 for i in result)

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

    def test_undo_my_changes(self):
        """Mirrors UI 9.4.4 — 'undo my changes' must map to direction=reset."""
        result = self._run_parse("undo my changes for the rest")
        assert result.get("direction") == "reset"

    def test_make_the_rest_a_bit_louder(self):
        """Mirrors UI 9.3.2 — covers the exact phrasing that timed out in manual testing.
        Previously the only failure was an LLM-side hang; behaviorally it should parse to
        feature=loudness, direction=up, magnitude=small, scope=rest."""
        result = self._run_parse("make the rest a bit louder")
        assert result.get("feature") == "loudness"
        assert result.get("direction") == "up"
        assert result.get("magnitude") == "small"
        assert result.get("scope") == "rest"
        assert result.get("needs_clarification") is False

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

    def test_unsupported_feature_clarifies_gracefully(self):
        """User asks for something the pipeline can't do (reverb, sparkle, tempo)
        — the graph must clarify, NOT crash, and must not silently coerce to a
        random supported feature. The PARSE_PROMPT now lists supported features
        and tells the LLM to redirect unsupported ones to the closest options."""
        result = self._run_parse("make it more sparkly")
        assert result.get("feature") in (None, "presence"), (
            f"Unsupported 'sparkly' should be redirected (presence is the closest legal "
            f"answer) or left null with a clarification — got feature={result.get('feature')!r}"
        )
        # If the LLM picked `null`, it must also flag for clarification so the user is unblocked.
        if result.get("feature") is None:
            assert result.get("needs_clarification") is True
            assert result.get("clarification_question")
            assert result.get("clarification_options")

    def test_clarification_options_no_internal_codes(self):
        """LLM-generated menu options are user-facing and must NOT contain
        parenthesized direction tags like '(up)' / '(down)' — those leaked into
        the UI before the prompt was tightened on 2026-05-01."""
        result = self._run_parse("noise reduction please")
        opts = result.get("clarification_options") or []
        for opt in opts:
            low = opt.lower()
            assert "(up)" not in low and "(down)" not in low, (
                f"Clarification option leaked internal direction tag: {opt!r}"
            )
            assert "(rest)" not in low and "(current)" not in low and "(next_tanda)" not in low, (
                f"Clarification option leaked internal scope tag: {opt!r}"
            )


# ── End-to-end execution tests (no LLM — state built post-parse) ──────────────
# These cover the UI_TEST_GUIDE rows that were previously "human only":
#   9.2.3 — `data/processed/` files get a fresh mtime after an audio adjustment
#   9.2.5 — the adjustment is "audibly" effective — proven here as a measurable
#           param shift (eq_vocal_gain reduced when feature=presence + direction=down)
#           plus the resulting WAV bytes differing from a baseline run.

def _make_synthetic_wav(path: Path, freq: float = 440.0, seconds: float = 3.0,
                        sr: int = 44100) -> Path:
    """Sine + a noise floor — enough signal for analyze_tanda_tracks to measure."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * freq * t)
    noise = 0.02 * np.random.RandomState(0).standard_normal(t.shape)
    audio = (tone + noise).astype(np.float32)
    sf.write(str(path), audio, sr)
    return path


def _post_parse_state(playlist, current_index, resolved_paths, output_dir,
                      *, scope, feature, direction, magnitude="medium"):
    """Build an AdjustmentState as if parse_request had already filled it in.
    Lets us exercise the downstream nodes without spending an LLM call."""
    return {
        "user_message": "(stubbed)",
        "playlist": playlist,
        "current_index": current_index,
        "output_dir": str(output_dir),
        "resolved_paths": resolved_paths,
        "scope": scope,
        "feature": feature,
        "direction": direction,
        "magnitude": magnitude,
        "target_name": None,
        "needs_clarification": False,
        "clarification_question": "",
        "clarification_options": [],
        "rejected": False,
        "rejection_options": [],
        "target_indices": [],
        "reference_params": None,
        "computed_overrides": [],
        "execution_results": [],
        "reply": "",
        "activity_log": [],
        "resolution_outcome": None,
    }


def _run_post_parse(state):
    """Run the deterministic part of the graph (resolve → measure → compute → execute).
    Skips parse_request (LLM) and format_reply (cosmetic)."""
    state.update(resolve_targets_node(state))
    state.update(measure_reference(state))
    state.update(compute_adjustments(state))
    state.update(execute_enhancement(state))
    return state


class TestAdjustmentExecutionEndToEnd:
    """Replaces UI_TEST_GUIDE rows 9.2.3 and 9.2.5 — both were 'human only' before."""

    def test_processed_file_mtime_updates_after_adjustment(self, tmp_path):
        """9.2.3 — after a chat audio adjustment, the corresponding `_enhanced.wav`
        in `output_dir` must have a NEWER mtime than before. Proves the pipeline
        actually re-ran rather than reusing the stale file."""
        raw = _make_synthetic_wav(tmp_path / "track_a.wav")
        out_dir = tmp_path / "processed"

        playlist = [
            {"type": "song", "title": "Now", "orchestra": "X", "style": "TANGO", "tanda_id": 0},
            {"type": "song", "title": "Target", "orchestra": "X", "style": "TANGO", "tanda_id": 0},
        ]
        # Note: current_index=0, so target=index 1 (the "rest" of the playlist).
        resolved_paths = {0: str(raw), 1: str(raw)}

        # Baseline run — pretend an earlier auto-enhance produced the file.
        state1 = _post_parse_state(
            playlist, current_index=0, resolved_paths=resolved_paths,
            output_dir=out_dir,
            scope="rest", feature="presence", direction="down", magnitude="medium",
        )
        state1 = _run_post_parse(state1)
        assert state1["execution_results"], "Baseline enhancement must produce a result"
        out_path = Path(state1["execution_results"][0]["output_path"])
        assert out_path.exists(), f"Enhanced file not written: {out_path}"
        mtime_before = out_path.stat().st_mtime

        # Force a measurable mtime gap regardless of filesystem resolution.
        time.sleep(1.1)

        # Second run — the adjustment graph re-runs and overwrites the file.
        state2 = _post_parse_state(
            playlist, current_index=0, resolved_paths=resolved_paths,
            output_dir=out_dir,
            scope="rest", feature="presence", direction="down", magnitude="large",
        )
        state2 = _run_post_parse(state2)
        assert state2["execution_results"], "Second enhancement must produce a result"
        mtime_after = out_path.stat().st_mtime

        assert mtime_after > mtime_before, (
            f"Adjustment did not refresh the enhanced file — mtime stayed at {mtime_before} "
            f"(after run: {mtime_after}). Pipeline likely short-circuited."
        )

    def test_presence_down_lowers_eq_vocal_gain_and_changes_output(self, tmp_path):
        """9.2.5 — 'audibly less harsh' is subjective, but the *measurable proxy*
        is concrete: feature=presence + direction=down must lower `eq_vocal_gain`
        below the auto-adaptive value, AND the resulting WAV bytes must differ
        from the same input enhanced with no override."""
        from atdj.audio.enhancement import enhance_tanda
        raw = _make_synthetic_wav(tmp_path / "track.wav")

        playlist = [
            {"type": "song", "title": "Now", "orchestra": "X", "style": "TANGO", "tanda_id": 0},
            {"type": "song", "title": "Target", "orchestra": "X", "style": "TANGO", "tanda_id": 0},
        ]
        resolved_paths = {0: str(raw), 1: str(raw)}

        # Baseline: enhance with no overrides (fully adaptive) by calling
        # enhance_tanda directly. (Post-2026-05-01, the graph's direction=reset
        # path deletes the processed file rather than producing one, since the
        # auto-enhance-on-PLAN hook was removed.)
        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        baseline_results = enhance_tanda([Path(raw)], baseline_dir, param_overrides=None)
        baseline_path = Path(baseline_results[0]["output_path"])
        baseline_bytes = baseline_path.read_bytes()

        # Adjusted: feature=presence, direction=down — should lower eq_vocal_gain.
        adjusted_dir = tmp_path / "adjusted"
        state_adjusted = _post_parse_state(
            playlist, current_index=0, resolved_paths=resolved_paths,
            output_dir=adjusted_dir,
            scope="rest", feature="presence", direction="down", magnitude="large",
        )
        state_adjusted = _run_post_parse(state_adjusted)

        # 1. The override applied to the target track must lower eq_vocal_gain.
        overrides = state_adjusted["computed_overrides"]
        assert overrides and "eq_vocal_gain" in overrides[0], (
            f"compute_adjustments did not produce an eq_vocal_gain override: {overrides!r}"
        )
        adjusted_gain = overrides[0]["eq_vocal_gain"]
        # The default reference for presence is 1.5 (atdj/audio/adjustment_graph.py:DEFAULT_PARAMS).
        # `large` magnitude is 2.0 → requested target = 1.5 - 2.0 = -0.5.
        # apply_constraint takes min(track_auto_value, requested_target) for direction=down,
        # so adjusted_gain must be <= -0.5 (or <= track auto value, whichever is lower).
        assert adjusted_gain <= -0.5 + 1e-6, (
            f"presence/down/large should lower eq_vocal_gain to <=-0.5 (got {adjusted_gain})"
        )

        # 2. The output bytes must differ from the baseline — proves the override
        #    actually changed the audio, not just the parameter on paper.
        adjusted_path = Path(state_adjusted["execution_results"][0]["output_path"])
        adjusted_bytes = adjusted_path.read_bytes()
        assert adjusted_bytes != baseline_bytes, (
            "Adjusted WAV is byte-identical to the baseline — the eq_vocal_gain override "
            "did not propagate to the audio output. The pipeline likely ignored the override."
        )
