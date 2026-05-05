# Test Suite — AT-DJ

Run all tests:
```
uv run pytest tests/ -v
```

The suite is organized by area (schemas, playback, audio enhancement, RAG). Per-area scope and notable coverage is summarized below — for individual test names, run `pytest --collect-only`.

---

## tests/test_schemas.py — Pydantic schema validation

Smoke + boundary tests for the four Pydantic models in `atdj/schemas/`. Pure in-memory data; no audio files, no catalog.

Covers:
- **Track:** valid construction, `duration_seconds > 0`, optional features default to `None`.
- **Tanda:** valid 3-track tanda, length bounds (3–4 tracks), style-homogeneity validator (mixed styles raise; mixed orchestras allowed because that's a soft rule), `energy_level` range.
- **FeedbackEvent:** valid event, unrecognised `event_type` raises.

---

## tests/test_playback.py — PlaybackQueue engine

Pure-Python tests for `PlaybackQueue` (the cursor-managed playlist that drives the Now Playing card). No Streamlit, no audio decoding.

Covers:
- Queue navigation (next / prev / skip; behaviour at the start and end of the queue).
- Play / pause / stop transport state.
- Session-state round-trip (serialize and rehydrate across Streamlit reruns).
- Duration parsing for both string (`"3:00"`) and float seconds.
- Reorder (move up / down) and remove operations, including cursor adjustment when an item before or at the cursor is removed.
- **TandaId renumbering:** the `_renumber_tanda_ids` migration that heals stacked-plan collisions so `next_tanda` adjustments don't accidentally target every tanda with the same per-plan index.

---

## tests/test_audio_resolution.py — Catalog filename resolution sweep

Verifies every row in the feature catalog (`data/essentia_newsamp.csv`) resolves to an audio file on disk via `PlaybackQueue.resolve_file_path`. Pure I/O; no LLM, no Streamlit, no audio decoding.

Covers:
- A parametrized check across all ~294 catalog rows — each `(title, orchestra)` must resolve to a real file. Catches filename-encoding regressions (cp437-corrupted accents, cortina-vs-raw mismatches, missing files).
- An aggregate summary test that fails once with the full list of unresolved rows so a single report shows total damage.
- Cortina resolution spot-check against a known cortina filename.

Replaces the manual UI walkthrough of special-character filenames.

---

## tests/test_audio_enhancement/ — DSP pipeline + adjustment graph

Three files covering the full audio-enhancement stack from synthetic-audio unit tests up through the chat-driven LangGraph.

### test_enhancement.py — DSP analysis and pipeline

Synthetic audio (sine + white noise); no real audio files needed.
- **Analysis utilities:** SNR measurement (positive on clean signal, lower on noisy), spectral centroid in plausible range, music-cutoff floor.
- **Pipeline:** SNR improves after enhancement, no clipping, output LUFS lands near target, output WAV is created (including in fresh subdirectories), zero-EQ run still cleans up SNR.
- **Adaptive parameters:** noisier track gets a more aggressive `noise_prop` than a cleaner track in the same tanda.

### test_enhancement_params.py — Exposed parameter overrides

Synthetic 44.1 kHz WAV; tests the parameters that were lifted out of the pipeline interior so the agent can override them.
- `enhance_track`: defaults still produce output and metrics; custom highpass / limiter threshold / target LUFS values run cleanly; `hiss_cutoff_override` bypasses auto-detection; `output_path=None` returns metrics without writing.
- `enhance_tanda`: backward compatibility (no overrides), per-track override application, partial overrides merging with adaptive baselines, `None` and empty-dict behaviour matching no-arg behaviour.

### test_adjustment_graph.py — Natural-language audio adjustment graph

Tests the LangGraph in `atdj/audio/adjustment_graph.py`. Pure-logic tests run with no LLM; integration tests need an LLM API key.

- **Constraint logic** (relative floor/ceiling): up-direction lifts tracks below target and leaves tracks already above untouched; down-direction is the mirror; reset returns the per-track adaptive value; same logic generalizes from LUFS to EQ-gain parameters.
- **Scope-to-index resolution:** `rest`, `next_song`, `next_tanda`, `specific` (by orchestra or style, case-insensitive), and the cortina-skipping behaviour. Includes the regression test for the "next_tanda must return ONE tanda, not all subsequent" bug.
- **Parse-request integration** (LLM, marked `integration`): natural-language prompts map to the correct `feature` / `direction` / `magnitude` / `scope` / `target_name`; ambiguous prompts trigger clarification; clarification-option labels never leak internal codes; unsupported features either get redirected to the closest legal one or trigger a clean clarification.
- **End-to-end execution:** parsed state → resolve targets → measure reference → compute adjustments → execute enhancement → output WAV. Two anchor tests confirm the processed-file mtime updates after a run, and that down-direction on `presence` actually lowers the corresponding EQ gain and produces audibly different output bytes.

---

## tests/test_rag/ — Retrieval and Q&A

Seven files covering the RAG stack from low-level fetch up through the user-facing answer.

- **test_fetch_simple.py / test_fetch_complex.py:** `fetch_knowledge` returns the expected source priority — local markdown first, then Wikipedia — for both simple lookups (orchestra name) and complex multi-clause queries.
- **test_query_track_retrieval.py:** ChromaDB-backed `retrieve_tracks` honours metadata filters (e.g. decade) and returns the expected number of hits.
- **test_search_for_planning.py:** the planner-facing search path returns era-appropriate tracks (e.g. a "1930s tango" query produces 1930s tango candidates).
- **test_answer_feature.py:** structured answers about specific Track fields (BPM, year) come back as expected.
- **test_answer_question_smoke.py:** `answer_question` returns a non-empty string for a generic query (sanity check, no semantic assertion).
- **test_answer_question_real.py:** end-to-end Q&A through a real LLM call (slow; requires API key).

Run only the fast subset with:
```
uv run pytest tests/ -v -m "not integration"
```

---

## Running notes

- Integration tests (LLM-backed) are marked with `@pytest.mark.integration` and require an Anthropic or Gemini API key in `.env`. Skip them with `-m "not integration"`.
- Audio-resolution and enhancement tests need `data/essentia_newsamp.csv` and the corresponding files in `data/raw/` and `data/cortinas/`; missing files surface as a single aggregated failure.
- The full suite collects ~399 tests as of 2026-05-03.
