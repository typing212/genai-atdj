# Changes After Merge

**Branch:** `vanessaz` · **Merge commit:** `25ccaf5`

Post-merge edits to teammates' code on the `nancy-upload + tina` merge. This file tracks the changes from 2026-05-01 onwards; earlier post-merge work has been retired from this log.

---

## 2026-05-01

### Removed Quality Enhance toggle + auto-enhance-on-PLAN hook
The sidebar/playback-controls **Quality Enhance** toggle and the PLAN handler's auto-enhance block are gone. Audio enhancement now ONLY fires from the chat path (`atdj/audio/adjustment_graph.py`). What changed:

- `atdj/ui/page_main.py`: removed the `st.toggle("Quality Enhance", key="auto_enhance")` widget and its `_on_qe_toggle` handler; collapsed the audio-settings 3-column layout to 2; deleted the auto-enhance block that called `enhance_tanda` after PLAN; removed the `stored_adjustment_intent` writer.
- `atdj/audio/adjustment_graph.py`: removed `auto_enhance_on`, `store_intent`, `intent_to_store` from `AdjustmentState`; deleted `compute_intent_overrides()` (only used by the now-removed PLAN hook); simplified `execute_enhancement` so `direction=reset` always deletes the processed file (since nothing else maintains one) and we never set `store_intent`.
- `tests/test_audio_enhancement/test_adjustment_graph.py`: dropped `TestComputeIntentOverrides` (7 tests, all about the removed function); removed `auto_enhance_on/store_intent/intent_to_store` from the post-parse helpers; one end-to-end test now generates its baseline by calling `enhance_tanda` directly instead of relying on the old `direction=reset` "no-overrides" code path.
- `tests/UI_TEST_GUIDE.md`: rows 1.7 and 5.5 (Quality Enhance toggle), all of Test 8 (auto-enhance hook), and section 9.7 (persistence) marked as removed.

### Audio adjustment — four fixes from manual testing

1. **`next_tanda` returned 12 tracks across multiple plans.** `page_main.py` was writing `tanda_id = tanda_idx` (the per-plan enumerate index), so every fresh PLAN restarted at id 0. With 5 plans queued the playlist had multiple songs sharing each id, and `resolve_targets("next_tanda")` matched all of them. Fix: compute `_tanda_id_offset = max(existing tanda_ids) + 1` once per PLAN and write `tanda_id = _tanda_id_offset + tanda_idx`. The user-search-add path at line 1557 was already doing this correctly — the agent path now matches.
2. **Clarification options leaked internal codes** like `"Reduce noise (down)"` into the on-screen menu. `PARSE_PROMPT` (`atdj/audio/adjustment_graph.py`) gained explicit rules: write user-facing labels in plain English; never include parenthesized direction/scope/feature tags; examples of good vs bad. New integration test `test_clarification_options_no_internal_codes` enforces it.
3. **State not preserved across clarification turns.** After a user picked a menu option (e.g. `"Reduce noise"`), `parse_request` saw only that short text, the LLM returned `needs_clarification=true` for whatever slot was still missing, and the prior turn's already-resolved feature/direction got re-asked forever. The earlier "fall back to prior state for null fields" fix wasn't enough on its own. New rule: after merging the LLM's parse with prior state, if `feature + direction + scope` are all filled (or `direction=reset + scope`), force `needs_clarification=False` regardless of what the LLM said.
4. **Unsupported-feature requests** like `"make it more sparkly"` or `"add reverb"` weren't covered. `PARSE_PROMPT` now tells the LLM: if the request is not one of the six supported features, set `feature=null`, set `needs_clarification=true`, briefly explain what IS supported, and offer the closest legal options. New integration test `test_unsupported_feature_clarifies_gracefully` covers it.

### Catalog filename resolution — automated sweep test (`tests/test_audio_resolution.py`)
The cp437-corrupted-filename rename (24 files renamed via `s.encode("cp437").decode("utf-8")` round-trip + NFC) was previously verified by hand for a handful of titles in UI test 7.10. That step is now an automated pytest sweep:

- `tests/test_audio_resolution.py` parametrizes `PlaybackQueue.resolve_file_path` over every row of `data/essentia_newsamp.csv` (294 rows) and asserts the resolved path exists on disk. A second `test_resolution_summary` aggregates failures into one report. A third `test_cortina_resolves_when_directory_present` smoke-checks the cortina branch.
- Run: `uv run pytest tests/test_audio_resolution.py -v` — currently 296 passed.
- `tests/UI_TEST_GUIDE.md` step 7.10 is now a stub that points at the automated test.
- `tests/README.md` documents the new test under its own section.
