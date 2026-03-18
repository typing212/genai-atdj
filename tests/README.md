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

## Upcoming tests (added per WP)

| File | WP | What it will cover |
|---|---|---|
| `test_audio_metadata.py` | WP-02 | `read_metadata()` parses ID3 tags; `infer_track_type()` detects cortinas |
| `test_audio_features.py` | WP-02 | `extract_features()` returns values in plausible ranges |
| `test_validator.py` | WP-05 | Tanda rule enforcement; energy arc build and adjust |
| `test_agent.py` | WP-06 | Agent state transitions; tool call routing |
| `test_rag.py` | WP-07 | ChromaDB ingest and retrieval round-trip |
