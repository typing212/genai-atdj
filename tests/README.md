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

## Upcoming tests (added per WP)

| File | WP | What it will cover |
|---|---|---|
| `test_audio_metadata.py` | WP-02 | `read_metadata()` parses ID3 tags; `infer_track_type()` detects cortinas |
| `test_audio_features.py` | WP-02 | `extract_features()` returns values in plausible ranges |
| `test_validator.py` | WP-05 | Tanda rule enforcement; energy arc build and adjust |
| `test_agent.py` | WP-06 | Agent state transitions; tool call routing |
| `test_rag.py` | WP-07 | ChromaDB ingest and retrieval round-trip |
