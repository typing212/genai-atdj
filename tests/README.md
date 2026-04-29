# Test Suite — AT-DJ

Run all tests with:
```
uv run pytest tests/ -v
```

---

## test_schemas.py — Pydantic Schema Validation (WP-01)

Tests that all four data schemas enforce their constraints correctly.
Uses dummy in-memory data only — no audio files, no catalog.csv required.

### Track tests

| Test | What it checks |
|---|---|
| `test_valid_track` | A well-formed Track instantiates without error; enum values are stored as strings |
| `test_track_negative_duration` | `duration_seconds <= 0` raises a validation error |
| `test_track_optional_features_default_none` | `bpm`, `energy`, `key` default to `None` before extraction runs |

### Tanda tests

| Test | What it checks |
|---|---|
| `test_valid_tanda` | 3 same-style tracks form a valid Tanda; `total_duration_seconds` is auto-computed |
| `test_tanda_too_few_tracks` | Fewer than 3 tracks raises a validation error |
| `test_tanda_too_many_tracks` | More than 4 tracks raises a validation error |
| `test_tanda_mixed_orchestras_allowed` | Mixed orchestras pass schema validation — orchestra homogeneity is a soft rule enforced by the planner in WP-05, not Pydantic |
| `test_tanda_mixed_styles` | Tracks of different styles raises `ValueError` — style is always hard |
| `test_tanda_energy_out_of_range` | `energy_level > 1.0` raises a validation error |

### FeedbackEvent tests

| Test | What it checks |
|---|---|
| `test_valid_feedback_event` | A valid event type instantiates correctly; `processed` defaults to `False` |
| `test_invalid_feedback_event_type` | An unrecognised `event_type` string raises a validation error |

---

## test_playback.py — PlaybackQueue Engine (WP-04)

Tests the `PlaybackQueue` class that drives the UI's Now Playing section.
Pure Python unit tests — no Streamlit, no audio files required.

### Queue navigation

| Test | What it checks |
|---|---|
| `test_current_track_empty_queue` | Empty queue returns `None` |
| `test_current_track_returns_first` | First item is returned on a fresh queue |
| `test_next_track_advances` | `next_track()` moves index forward and returns the correct item |
| `test_next_track_at_end_returns_none` | At end of queue, returns `None` and sets `is_playing` to `False` |
| `test_previous_track_at_start` | At index 0, stays at 0 and returns the first track |
| `test_previous_track_goes_back` | Moves index backward and returns the correct item |
| `test_skip_is_next` | `skip()` behaves identically to `next_track()` |

### Playback controls

| Test | What it checks |
|---|---|
| `test_play_pause_toggle` | `play_pause()` toggles `is_playing` between `True` and `False` |
| `test_stop_resets` | `stop()` sets `is_playing` to `False` |

### Session state persistence

| Test | What it checks |
|---|---|
| `test_session_state_roundtrip` | `to_session_state()` → `from_session_state()` preserves index, playing state, and all items |

### Duration parsing

| Test | What it checks |
|---|---|
| `test_get_current_duration_from_string` | Parses `"3:00"` format to `180.0` seconds |
| `test_get_current_duration_from_seconds` | Reads `duration_seconds` float directly when available |

### Reorder & remove

| Test | What it checks |
|---|---|
| `test_move_up` | Swaps item with the one above; indices update correctly |
| `test_move_up_at_zero` | Returns `False` when already at top — no-op |
| `test_move_down` | Swaps item with the one below; indices update correctly |
| `test_remove_before_cursor` | Removing an item before the cursor adjusts current index down by 1 |
| `test_remove_at_cursor` | Removing the current item advances to the next track |

---

## test_enhancement.py — Audio Enhancement Pipeline (WP-08)

Tests the audio enhancement pipeline using synthetic audio (sine wave + white noise). No real audio files needed.

### Analysis functions

| Test | What it checks |
|---|---|
| `test_measure_snr_positive` | Clean signal returns positive SNR |
| `test_measure_snr_noisy_lower` | Noisier signal has lower SNR than clean signal |
| `test_find_music_cutoff_respects_min` | Cutoff frequency never goes below the safety floor (5kHz) |
| `test_measure_spectral_centroid_range` | Spectral centroid is within plausible range (100 Hz – Nyquist) |

### Enhancement pipeline

| Test | What it checks |
|---|---|
| `test_enhance_improves_snr` | SNR after enhancement > SNR before |
| `test_no_clipping` | Peak amplitude never exceeds 1.0 |
| `test_lufs_near_target` | Output LUFS within 6 LU of target (dynamic hiss filter shifts LUFS after normalization) |
| `test_output_file_created` | Output WAV file exists, including when subdirectory needs creation |
| `test_flat_eq_no_boost` | Zero EQ gains still improves SNR (pipeline works without EQ boost) |

### Adaptive parameters

| Test | What it checks |
|---|---|
| `test_compute_per_track_params_adaptive` | Noisier track gets higher `noise_prop` than cleaner track |

---

---

## test_enhancement_params.py — Exposed Enhancement Parameters

Tests the three parameters that were previously hardcoded inside `enhance_track()` and
the new `param_overrides` argument on `enhance_tanda()`. Uses synthetic WAV audio at
44100 Hz — no real audio files needed.

Run only this file:
```
uv run pytest tests/test_enhancement_params.py -v
```

### enhance_track() new params

| Test | What it checks |
|---|---|
| `test_default_params_unchanged_behavior` | Calling with all defaults still produces output and metrics |
| `test_custom_highpass_runs_without_error` | `highpass_hz=120.0` is accepted and pipeline completes |
| `test_custom_lowered_highpass` | `highpass_hz=60.0` is accepted and pipeline completes |
| `test_custom_limiter_threshold` | `limiter_threshold_db=-3.0` is accepted and pipeline completes |
| `test_hiss_cutoff_override_disables_auto_detect` | When `hiss_cutoff_override=8000.0`, the returned `hiss_cutoff` matches the override exactly |
| `test_hiss_cutoff_none_uses_auto` | `hiss_cutoff_override=None` triggers auto-detection and returns a positive value |
| `test_custom_target_lufs` | Track enhanced to `-11.0` LUFS is louder than one enhanced to `-18.0` LUFS |
| `test_no_output_path_returns_metrics_only` | Passing `output_path=None` returns the metrics dict without writing a file |

### enhance_tanda() param_overrides

| Test | What it checks |
|---|---|
| `test_backward_compat_no_overrides` | Calling without `param_overrides` behaves identically to before |
| `test_param_overrides_applied` | Tracks enhanced with `target_lufs=-11.0` override are louder than default |
| `test_partial_overrides_merge_with_adaptive` | Overriding one track while leaving the other empty both complete without error |
| `test_none_overrides_same_as_no_arg` | `param_overrides=None` gives the same result count as omitting the argument |
| `test_empty_dict_overrides_use_adaptive` | `[{}, {}]` produces fully adaptive enhancement — same as no override |

---

## test_adjustment_graph.py — Natural-Language Audio Adjustment

Tests the mini LangGraph in `atdj/audio/adjustment_graph.py` that handles ADJUST_AUDIO
chat requests. Pure logic tests run with no LLM. Integration tests require `GOOGLE_API_KEY`.

Run pure logic tests only (fast, no API key needed):
```
uv run pytest tests/test_adjustment_graph.py -v -m "not integration"
```

Run integration tests (requires API key):
```
uv run pytest tests/test_adjustment_graph.py -v -m integration
```

### apply_constraint() — relative floor/ceiling logic

| Test | What it checks |
|---|---|
| `test_up_floor_track_already_higher` | Track already above target is left unchanged |
| `test_up_floor_track_lower_than_target` | Track below target is raised to the target |
| `test_up_floor_track_exactly_at_target` | Track at exactly the target stays at target |
| `test_down_ceiling_track_already_lower` | Track already below target is left unchanged |
| `test_down_ceiling_track_higher_than_target` | Track above target is lowered to target |
| `test_reset_returns_auto_value` | Reset direction returns the track's own adaptive value unchanged |
| `test_up_eq_gain_floor` | Same floor logic for EQ gain parameters |
| `test_down_eq_gain_ceiling` | Track already softer than target is left unchanged |
| `test_down_eq_gain_ceiling_applied` | Track louder than target is lowered |

### resolve_targets() — scope to playlist index mapping

| Test | What it checks |
|---|---|
| `test_rest_returns_all_songs_after_current` | scope=rest returns all song indices after current |
| `test_rest_skips_cortinas` | Cortina items are never included in results |
| `test_next_song_skips_cortina` | scope=next_song jumps over a cortina to reach the next song |
| `test_next_song_no_skip_needed` | scope=next_song returns immediately adjacent song when no cortina between |
| `test_next_tanda` | scope=next_tanda returns all songs with the next tanda_id |
| `test_next_tanda_from_second_tanda` | Works correctly from mid-session position |
| `test_next_tanda_no_more_tandas` | Returns empty list when no further tanda exists |
| `test_specific_by_orchestra` | scope=specific matches by orchestra name (case-insensitive) |
| `test_specific_by_style` | scope=specific matches by style |
| `test_specific_case_insensitive` | Uppercase target_name still matches correctly |
| `test_specific_no_match_returns_empty` | Unmatched target_name returns empty list |
| `test_no_songs_after_last_track` | Returns empty list when current is the last track |
| `test_rest_from_beginning` | scope=rest from index 0 returns all non-cortina tracks |

### compute_intent_overrides() — stored intent applied to new sessions

| Test | What it checks |
|---|---|
| `test_loudness_up_small_uses_default_reference` | Small up delta applied from DEFAULT_PARAMS baseline |
| `test_loudness_down_medium` | Medium down delta produces correct target value |
| `test_bass_up_large` | Large up delta on eq_low_gain produces correct target value |
| `test_reset_returns_empty_overrides` | Reset direction returns `{}` for every track |
| `test_unknown_feature_returns_empty` | Unrecognised feature name returns `{}` for every track |
| `test_track_count_respected` | Output list length always matches requested track count |
| `test_zero_tracks` | Zero track count returns an empty list |

### Integration tests (LLM — `@pytest.mark.integration`)

| Test | What it checks |
|---|---|
| `test_bass_down_small` | "turn down the bass a little" → feature=bass, direction=down, magnitude=small |
| `test_loudness_up_medium` | "too quiet, make it louder" → feature=loudness, direction=up |
| `test_current_song_scope` | "this song is too harsh" → scope=current |
| `test_rest_scope` | "everything after this is too noisy" → scope=rest, feature=noise |
| `test_reset_direction` | "go back to default" → direction=reset |
| `test_use_original` | "use original for the next tanda" → direction=reset |
| `test_named_target_orchestra` | "more presence in the Di Sarli tanda" → scope=specific, target_name contains "sarli" |
| `test_ambiguous_triggers_clarification` | "it sounds a bit off" → needs_clarification=True |

---

## Upcoming tests (added per WP)

| File | WP | What it will cover |
|---|---|---|
| `test_audio_metadata.py` | WP-02 | `read_metadata()` parses ID3 tags; `infer_track_type()` detects cortinas |
| `test_audio_features.py` | WP-02 | `extract_features()` returns values in plausible ranges |
| `test_validator.py` | WP-05 | Tanda rule enforcement; energy arc build and adjust |
| `test_agent.py` | WP-06 | Agent state transitions; tool call routing |
| `test_rag.py` | WP-07 | ChromaDB ingest and retrieval round-trip |
