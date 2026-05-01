# Changes After Merge

**Branch:** `vanessaz` · **Merge commit:** `25ccaf5` · **Started:** 2026-04-28

Post-merge edits made to teammates' code on top of the `nancy-upload + tina` merge. Documented by area.

---

## 2026-04-30 — new changes (post last sync)

Roommate sync note: everything in the dated section below is **after** the previous handoff. Older changes are documented further down by area.

### Removed chat input selectors
The two dropdowns next to the chat textarea — *Context* (`Any / Tanda Planning / Q&A / Audio Enhancement`) and *Mode* (`Convention / Flexible`) — were removed. Every prompt now flows through the LLM classifier (the previous "Any" path), which routes to PLAN / ADJUST_AUDIO / QUESTION. Concrete cleanups:
- `atdj/ui/page_main.py`: dropped `CHAT_CONTEXTS`, `PLANNING_DESCRIPTIONS`, both `st.selectbox` widgets, the `s_planning` initializer, the per-message context badge, and the `if context == ...` dispatch chain. Layout simplified to textarea + send button.
- `atdj/schemas/session.py`: removed the `planning_mode: Literal[...]` field from `PlanSession` (it was stored but never branched on).
- `atdj/schemas/README.md`: dropped the `planning_mode` table row and its behavior block.
- `tests/test_schemas.py`: removed three `test_session_planning_mode_*` tests.
- `tests/UI_TEST_GUIDE.md`: dropped "Set context to ..." instructions from steps 2.1, 2.8, 3.1, 4.1, 4.3, 9.1, 9.2.1; collapsed Test 9.1 (Routing) from three sub-steps to one; reworded the common-issues fix for misrouted `back to default`.
- `atdj/agent/nodes.py` (Tina): the `"planning_mode"` key on the session-summary log dict was **commented out** (not deleted) per the teammate-edit rule. It used `getattr(..., default=...)` so it would not have crashed after the schema change, but logging a removed field is misleading.

### Now Playing empty after Clear → re-plan — fixed in `atdj/playback/player.py` + `atdj/ui/page_main.py`
Discovered while running Test 5 (the Clear button + re-plan flow). After clicking **Clear** in the playlist header, then planning a fresh tanda, the playlist filled with new tracks but Now Playing kept showing the empty placeholder — and there was no affordance to manually pick a track to play.

Root cause: `pq.items.clear()` empties `_items` in place but leaves `_current_index` at whatever it was (e.g. 27 after a long milonga session of moves/removes). On the next plan, `pq.items.extend(new_playlist)` adds 4 tracks → `current_index=27 >= len(items)=4` → `current_track()` returns `None` → Now Playing renders the placeholder.

Fix:
- Added `PlaybackQueue.clear()` to `atdj/playback/player.py` — wipes items, resets `_current_index` to 0, sets `_is_playing` to False, all in one place.
- Switched `atdj/ui/page_main.py:1199` from `pq.items.clear()` to `pq.clear()`.

### Session Log redesign — categorized + collapsed
The on-screen Session Log was hard to read: each PLAN tanda emitted 3–5 lines (`[session_init]`, `[tanda_planner]`, `[cortina_selector]`, `[queue_publisher]`, `[session_summary]`), each audio adjustment emitted 4 lines from internal nodes, internal IDs and file paths leaked to the UI, and there was no easy way to tell which entry came from PLAN vs AUDIO vs the user. Redesign:

- **Categories with a prefix icon**: `📋 PLAN — …` (agent planning), `🎛 AUDIO — …` (agent audio enhancement), `👤 You — …` (user actions).
- **Two-layer log model**: every sub-step entry is still written to the `data/log/session_log_*.json` file for fault tracking; the on-screen log shows only the **summary entries** (one per logical event).
- **Schema change in `_log()` (Tina, both `atdj/agent/nodes.py` and `atdj/audio/adjustment_graph.py`)**: added a `summary: bool` field (default `False`) on each entry. Original lines are commented out; new alongside, per teammate-edit rule. Affected nodes:
  - `session_init` — its single entry is marked `summary=True` (it IS the milestone)
  - `queue_publisher` — keeps its detailed sub-step entry, *plus* emits one new `summary=True` entry per tanda combining tanda planner + cortina + publish into `Tanda K/N ready: N tracks (Orchestra)` (or `Tanda K/N skipped — no tracks` on failure)
  - `session_summary` — wording branched by outcome: all-succeeded → `Plan complete — N tandas ready`; mixed → `Plan complete — K of N tandas ready (M failed)`; all-failed → `Plan failed — no tandas could be planned`. Both the wrap-up line and the `Log saved to …` line are `summary=True` (the user wants the log-saved line on screen).
  - `format_reply` (audio) — keeps its detailed entry, *plus* emits one `summary=True` entry per audio request: e.g. `Slightly reduced vocal presence for 1 track`.
- **`atdj/ui/page_main.py`**: filters all `activity_log` hoists to `summary=True`, prefixes PLAN entries with `📋 PLAN — `, audio entries with `🎛 AUDIO — `; the `_log()` user-action helper auto-prefixes with `👤 You — `; the auto-enhance success/failure entries inside the PLAN handler are now prefixed `📋 PLAN — Auto-enhanced …` / `📋 PLAN — Enhancement skipped: …`.
- **Test 5.9 cleanup**: dropped the `_log` call in the new ▶ jump-to-track handlers (cortina + song rows) — jumping is pure navigation, not a state change worth logging.
- **Documentation**: tests in `tests/UI_TEST_GUIDE.md` referencing the old log strings (Test 2.5, Test 3.2–3.5, Test 5.x, Test 9.2.4) are updated to the new format.

### Q&A path import fix — `atdj/rag/store.py` (Nancy)
Discovered while running Test 4 (Q&A path) end-to-end for the first time. Importing `atdj.rag.query` failed at module load with `TypeError: unsupported operand type(s) for |: 'function' and 'NoneType'`, traced to:

```python
_chroma_client: chromadb.PersistentClient | None = None
```

In chromadb 1.5.8, `PersistentClient` is a function, not a class. PEP 604 union syntax (`X | Y`) on a function value is evaluated at module-load time and raises this TypeError. PLAN tests passed because they go through `atdj/agent/tools.py → rag/select_tanda.py`, which never imports `query.py`.

Per the teammate-edit rule, the original line is **commented out** and the new annotation is added alongside, using `Optional[...]` (already imported on line 19):

```python
# Original (Nancy): _chroma_client: chromadb.PersistentClient | None = None
# chromadb 1.5.8 exposes PersistentClient as a function; PEP 604 `func | None` at module level → TypeError.
_chroma_client: Optional[chromadb.PersistentClient] = None
```

---

## UI

### Empty initial state
The app no longer ships with demo data. Playlist, queue, energy chart, chat history, and Session Log all start empty. Only the DJ greeting in chat is preloaded.

### Sidebar simplified — Settings only
The "Sessions" panel (new-session button, scrollable list, rename/delete) was removed; it was never wired to real persistence, just in-memory display state. The sidebar now contains only Settings (provider, model, API key, Save Settings). The page header subtitle now shows today's date instead of an active-session label.

Side cleanups: removed the `SESSION_HISTORY` constant and the orphan `_section_log()` function (defined but never called).

### Session Log replaces hardcoded strings
The right-column log used to render fake strings. It now reads from `agent_notifications` in session state, populated by:
- `_log(text, kind)` — called by every user-driven action (move up/down, remove, Quality Enhance toggle, transition/cortina inputs, Clear button).
- `activity_log` entries returned by Tina's LangGraph nodes during PLAN.

Renamed from "Session Planning Log" to "Session Log" since it now covers everything. Tina's ISO-format timestamps are normalized to `HH:MM:SS` in the panel.

### Loading indicator polish
The user message now appears in chat immediately on send, with an italic placeholder reply ("Planning your session…", etc.) shown right below it. The duplicate `st.spinner` that used to render at the bottom of the page was removed — the in-chat placeholder already conveys the same affordance.

### Chat input clears on send
The textarea used to keep the user's message visible for the full agent run. Now it clears the moment the send button is clicked: the message is stashed in session state, the input key counter increments, `st.rerun()` fires, and the next render processes the stashed message against an empty fresh widget.

### Ctrl+Enter hint hidden
Streamlit's "Press Ctrl+Enter to apply" hint under the chat textarea was hidden via CSS — chat is sent via the ➤ button, not Ctrl+Enter, so the hint was misleading.

### Energy Arc chart (new visualization)
The Energy Arc panel in the music center is a new UI chart added post-merge. For each track in the playlist, it plots the catalog `energy` value against playlist position. Played tracks render as solid blue dots/lines; upcoming tracks as dashed grey. Hovering shows song / orchestra / singer / decade / source. Tracks without an energy value render as a hollow square at 50%.

The Y axis was initially mis-normalized: the chart was reading energy min/max from the playback catalog, which has no `energy` column. The KeyError was silently swallowed, falling back to a hardcoded range and producing values up to 2000%. Fixed by switching the lookup to the labeled RAG catalog (`_get_rag_catalog()`).

### Playlist append, not overwrite
A new plan used to replace the previous tanda because `pq_data` was reassigned from a fresh `PlaybackQueue`. Now the existing `pq` is loaded and the new tracks are appended.

### Clear All playlist button
Small "Clear" button added at the right of the **Full Playlist** header. Empties the queue, saves, and emits a log entry.

### Quality Enhance toggle defaults to OFF
The toggle next to the playback controls now defaults to **off** on first load. Auto-enhance was firing automatically before, surprising users and producing files in `data/processed/` they hadn't asked for. The two `st.session_state.get("auto_enhance", True)` reads in the PLAN handler were also flipped to `False` for consistency.

### Page rendered twice per script run — fixed
`main.py` did `from atdj.ui.app import run_app` (which triggered the module-level `run_app()` call at the bottom of `app.py` on import) and *then* called `run_app()` again on its own. The page rendered twice per script run, so every keyed widget (`sb_provider`, `sb_model`, `sb_api_key`, `new_session`, etc.) was registered twice — Streamlit raised `StreamlitDuplicateElementKey` intermittently, especially after hot-reloads. Fixed by commenting out the module-level call in `app.py`; `main.py` is now the single canonical entry point.

### KeyError guard on notifications
A few `agent_notifications.append()` call sites assumed the key existed. Normalized to `setdefault("agent_notifications", []).append()` so render order doesn't matter.

---

## Agent flow (PLAN path)

### What was wrong
The merged code had two parallel pipelines doing overlapping work:

1. **Tina's LangGraph** ran through `session_init → tanda_planner → cortina_selector → queue_publisher → session_summary` and emitted log entries. But `tanda_planner` called the LLM with tools bound (`search_catalog_rag`, `validate_tanda`, `get_energy_target`), no `ToolNode` was wired to execute the resulting tool call, and the response was discarded.
2. **A parallel selection block in `page_main.py`** (Tina's, verified via `git show origin/tina`) did the actual track selection by calling Nancy's translator and selector directly, bypassing the graph.

On top of that, the merge dropped the loop that pushed `activity_log` from the graph into the UI — the symbolic graph ran with all its log entries silently discarded, and the Session Log stayed empty.

### What changed
The PLAN path now runs through one canonical pipeline:

- The UI builds a `session_plan` (list of `(prompt, style)` tuples) and hands it into the graph as part of initial state.
- `tanda_planner` reads its per-tanda prompt from `session_plan[idx]` and calls `search_catalog_rag` directly. The LLM tool-binding round-trip is gone — saves one LLM call per tanda.
- `search_catalog_rag` wraps Nancy's translator + `_select_tanda`. The translator runs Layer 2 (the only LLM call left in the path); `_select_tanda` is deterministic scoring, no LLM.
- Selected tracks accumulate in `state["picked_tracks"]`. After `graph.invoke(...)` returns, the UI reads both `activity_log` (for the Session Log) and `picked_tracks` (for the playlist) from the final state.
- `search_catalog_rag` was previously hardcoded to `provider="gemini"` and `data/reduced_catalog.csv`. It now reads provider, model, and API key from the UI sidebar (`get_ui_provider/get_ui_model/get_ui_api_key`) and the catalog path from config. On failure, the returned error string includes the resolved provider/model/key-set state for diagnosis.

The original parallel block is preserved as a comment in `page_main.py` for traceability against Tina's branch.

### Reroute on empty tanda + honest log messages
The router previously always proceeded `tanda_planner → cortina_selector → queue_publisher` regardless of whether any tracks were selected. So a request that returned no matches still inserted a fake cortina and logged "Tanda N published to queue" — misleading.

`tanda_planner` now flips `needs_cortina` to `False` when the result is empty (or wrapped in an error), so the router skips straight to `queue_publisher`. A warning entry is emitted to the Session Log explaining the reason.

Several log messages were reworded to stop claiming success on failure:

- `session_init` previously: `"Session started — N tandas planned"` + `"Energy arc: …"`. Now: `"Plan started — N tanda(s) requested"`. The energy-arc line is dropped — the user-facing chart already shows actual selected-track energies.
- `tanda_planner` previously emitted `"Tanda N/M planned in X.Xs (… K tracks)"` regardless of outcome. Now only on success; on empty, emits a warning `"Tanda N/M failed in X.Xs — no tracks selected (reason)"`.
- `queue_publisher` previously logged `"Tanda N published to queue"` always. Now reads `last_agent_action`; on a failed tanda logs `"Tanda N skipped (no tracks)"` at warning level.
- `session_summary` previously: `"Session complete! Planned N tandas"` where N was the attempted count. Now reports successful vs attempted (e.g. `"Plan complete: 3 of 4 tanda(s) succeeded"`) at warning level when any failed.

All original lines preserved as commented-out blocks above the new code.

### Internal `energy_arc` removed from the graph
Tina's `session_init` originally computed a target energy curve and stored it in `state["energy_arc"]`. `tanda_planner` read it to derive a per-tanda mood for the LLM prompt; `queue_publisher` used its length as the canonical tanda count; `session_summary` saved it to the JSON log.

The curve was internal planning intent that never reached the user. The Energy Arc chart in the UI plots actual track energies, not the target. Once the LLM round-trip in `tanda_planner` was removed, the mood derivation became dead weight.

Removed: the `energy_arc` field from `AgentState`, the curve computation in `session_init`, the mood derivation in `tanda_planner`, the `len(state["energy_arc"])` reads in `tanda_planner`/`queue_publisher` (both now use `len(session_plan)`), the `energy_arc` entry in the `session_summary` JSON, and the `"energy_arc": []` slot in the UI's initial state. Originals preserved as comments.

### Session log JSON files relocated
Tina's `session_summary` writes one JSON per PLAN request — useful for debugging, but originally landed in `doc/`, polluting the documentation directory. Relocated the output path to `data/log/` (created with `parents=True, exist_ok=True`). Existing 24 logs were moved into the new location; `.gitignore` updated to exclude `data/log/*` (with `.gitkeep` so the empty folder stays in the tree). Original line preserved as a comment in `nodes.py`.

### Schema rename: `MilongaSession` → `PlanSession`
The schema (Vanessa's, from WP-01) was overloaded with the user-facing notion of a milonga session and had 14 fields, of which only 3 (`id`, `name`, `planning_mode`) were ever read by the running code. Renamed `PlanSession`, slimmed to those three fields, and now represents one agent planning run rather than a user-facing session.

`target_duration_minutes` (one of the dropped fields) was previously used by `session_init` to derive `total_tandas` via `duration // 15`. Now `total_tandas = len(state["session_plan"])`.

### Files touched
- `atdj/agent/state.py` — added `session_plan` + `picked_tracks`; removed `energy_arc`.
- `atdj/agent/tools.py` — UI-driven provider/model/key in `search_catalog_rag` (Nancy/Tina-territory wrapper, comment+add).
- `atdj/agent/nodes.py` — replaced `tanda_planner` LLM round-trip with direct `search_catalog_rag` invocation; reworded log messages; reroute on empty; dropped `energy_arc` references.
- `atdj/schemas/session.py` — class rename + slim.
- `atdj/ui/page_main.py` — builds `session_plan`, runs `graph.invoke`, reads `picked_tracks`; old parallel selection loop kept as comment.
- `tests/test_schemas.py` — updated to `PlanSession`.

---

## Audio enhancement feature

### Overview
Users can ask the DJ in plain language to adjust audio quality during a session — e.g. "the next tanda is too harsh", "make the rest a bit louder", "back to default". The agent figures out which tracks are affected, measures the currently playing song as a reference, and reprocesses the target tracks immediately. A reset path re-runs adaptive enhancement with no user overrides.

This also fixes a pre-existing bug: enhanced files were written to `data/processed/` but never played because the player always served raw files.

### How it works
- **Routing.** The chat classifier now has three categories instead of two: Tanda Planning, Q&A, and Audio Enhancement. The dropdown skips the classifier; otherwise the LLM picks one.
- **Intent parsing.** A dedicated mini LangGraph extracts four pieces from the user's message: scope (which tracks), feature (loudness / bass / presence / etc.), direction (up / down / reset), and magnitude (small / medium / large). Ambiguous messages prompt a clarification question. Requests targeting the currently playing track are rejected with alternatives.
- **Reference-based adjustment.** The target value is computed relative to what the current song measures, not as an absolute. Tracks already above the target are left unchanged.
- **Immediate processing.** All target tracks are enhanced in one batch when the user sends the request.
- **Persistence.** If auto-enhance is on, the adjustment is saved and applied to future planned sessions. If off, it applies only to the current playlist.

### Files touched
| File | Change |
|---|---|
| `atdj/audio/adjustment_graph.py` | New file — the mini LangGraph |
| `atdj/audio/enhancement.py` | Three previously hardcoded pipeline parameters now overridable; `enhance_tanda()` accepts per-track override dicts |
| `atdj/playback/player.py` | Now checks `data/processed/` before `data/raw/`; new method to always return the raw path for re-processing |
| `atdj/ui/page_main.py` | Chat dropdown updated; classifier extended; audio routing block added; PLAN handler applies any stored adjustment intent |
| `tests/test_audio_enhancement/test_adjustment_graph.py` | New — 29 logic tests + 8 LLM integration tests |
| `tests/test_audio_enhancement/test_enhancement_params.py` | New — 13 tests for the exposed parameters |
| `pyproject.toml` | `integration` pytest mark registered |

---

## RAG layer

### Catalog mismatch fixed
`_get_rag_catalog()` and `_get_rag_translator()` were loading `rag_catalog.csv`, but the translator requires four label columns (`bpm_label`, `danceability_label`, `chords_changes_rate`, `energy_label`) that exist only in `reduced_catalog.csv`. The PLAN path crashed on the first translator call.

Added a `REDUCED_CATALOG_PATH` constant in config and pointed both helpers at it. `RAG_CATALOG_PATH` is unchanged and still drives ChromaDB ingestion.

### Ingest path fix after config rename
Nancy's `ingest.py` originally imported `CATALOG_PATH`, which on her branch pointed to `rag_catalog.csv`. During the merge `CATALOG_PATH` was reassigned to the playback feature CSV (`essentia_newsamp.csv`), breaking the ingest. Added `RAG_CATALOG_PATH` and updated the ingest import to use it.

### Gemini 429 fallback in fetch and query
`fetch._normalize_query_for_lookup()` and `query.answer_question()` previously crashed when Gemini returned a rate-limit error. They now catch the error and fall back to Claude via the Anthropic SDK. In `fetch`, there's a final no-LLM fallback (keyword extraction) so the function always returns a usable lookup query. In `query`, the Claude response is duck-typed to match LangChain's interface.

### Performance — caching
Every Streamlit rerun used to recreate the ChromaDB client, re-read the catalog, and rebuild the translator. Three caches added:

- `atdj/rag/store.py` — module-level singleton for the ChromaDB client (and the sentence-transformers embedding model it loads).
- `atdj/ui/page_main.py` — `_load_catalog()` and `_get_rag_catalog()` use `@st.cache_data`. `_get_rag_translator(provider)` uses `@st.cache_resource` (the translator wraps a non-serializable LLM client). The cache is keyed by provider, so switching providers in the sidebar produces a fresh translator.

First load is still heavy (sentence-transformers initialisation); reruns and interactions after that are fast.

---

## Configuration & dependencies

### LLM provider selection from the UI
All LLM calls used to read provider/model/key from `.env` regardless of what the user entered in the sidebar. A new factory `get_ui_llm()` in `atdj/config.py` reads `s_provider`, `s_model`, and `s_api_key` from session state, falls back to `.env` outside Streamlit, and returns either `ChatAnthropic` or `ChatGoogleGenerativeAI`. Every `_get_llm()` site across the codebase now calls this factory.

The RAG prompt translator (in `page_main.py`) was hardcoded to `provider="gemini"` — broke the PLAN path whenever the Gemini key was missing or invalid. Now reads the sidebar provider.

`langchain-anthropic` was added as a dependency to support the Claude path.

### Env var rename: `GOOGLE_API_KEY` → `GEMINI_API_KEY`
The Gemini key was historically named `GOOGLE_API_KEY`, inconsistent with `GEMINI_MODEL`. Renamed to `GEMINI_API_KEY` everywhere; `GOOGLE_API_KEY` is still honoured as a fallback so existing `.env` files keep working.

### Files touched
- `atdj/config.py` — new factory + env var rename.
- `atdj/agent/nodes.py`, `atdj/audio/adjustment_graph.py`, `atdj/rag/query.py`, `atdj/rag/fetch.py`, `atdj/ui/page_main.py` — every `_get_llm()` site now goes through the factory.
- `atdj/rag/prompt_to_features.py` (Nancy's, comment+add) — `GeminiTranslator` reads `GEMINI_API_KEY` first, falls back to `GOOGLE_API_KEY`.
- `pyproject.toml` — `langchain-anthropic` added.
- `.env.example`, `README.md`, `tests/UI_TEST_GUIDE.md`, `tests/README.md`, `tests/test_audio_enhancement/test_adjustment_graph.py` — env var name updated in docs/tests.

---

## Data and assets

### Audio file rename
Files in `data/raw/` were stored as `Vol-XX La Fiesta De Buenos Aires__NN <Title>.mp3`, but the catalog stored just `NN <title>.mp3` in the `filename` column. The player's lookup never matched. All 294 files were renamed to drop the album prefix and double-underscore. No collisions, no code changes.

---

## TODOs / Future work

Open items deferred from this round of post-merge work.

### 1. Multi-tanda detection + planning
The current `is_full_session` detector in `page_main.py` only triggers on a narrow keyword list (`full`, `session`, `milonga night`, `complete`, `tonight`). Phrases like `"3 more tandas in the sequence of tango tango milonga"` slip through and get planned as a single tanda. Need to:
- Parse explicit counts (`\b(\d+)\s+tandas?\b`) and explicit style sequences (`tango tango milonga`) from the user's prompt.
- Build the `session_plan` with the detected count and style ordering.
- Decide what to do when the user gives a count without styles (default to all-tango? infer from context?).

### 2. Energy continuity across tandas
Right now each tanda is planned independently against its own prompt. The Energy Arc chart shows actual track energies, but consecutive tandas can have a jarring energy jump because there's no constraint linking the END of one tanda to the START of the next. Need to:
- After picking each tanda, pass the last track's energy as a "starting hint" to the next tanda's selection.
- Optionally smooth the cross-tanda transition (e.g., bias the first track of tanda N+1 to be near the energy of the last track of tanda N).
- Consider exposing a "smoothness" knob in the UI for the user to control how strict the transition should be.

### 3. Handle nonsensical / off-topic prompts in PLAN context
When the user types something meaningless (e.g., random characters, off-topic small talk like `"hello"`, or a request that's not actually a tanda) with the **Tanda Planning** context selected, the agent still runs the full graph and either returns a low-quality match or fails with `no candidates matched the prompt`. Need to:
- Detect non-planning input (e.g., a quick LLM check or heuristic on prompt structure / known keywords).
- Either reply with a clarification question (`"That doesn't look like a tanda request — did you mean ___?"`) or route to Q&A automatically.
- Decide the desired behavior when the input is ambiguous but not garbage (`"play something nice"`).

### 4. Finish the UI test guide sweep
Tests 1, 2, 3, 8.1, and 10 in `tests/UI_TEST_GUIDE.md` are recorded PASS as of 2026-04-29. The rest still need to be walked through and checked off:
- **Test 4** — Q&A path (RAG pipeline answers tango knowledge questions).
- **Test 5** — Session Log captures user actions (move up/down/remove, Clear, toggle, transition/cortina inputs, timestamp formatting).
- **Test 6** — Energy Arc chart (rendering, hover, color states, manual library add).
- **Test 7** — Playback controls (next/prev/end-of-queue/remove-while-playing).
- **Test 8** — Auto-enhance hook on PLAN (8.2-8.6: toggle ON/OFF, processed files appearance, player path).
- **Test 9** — Audio Enhancement chat path (routing, standard adjustment, relative constraint, reset, current-song rejection, clarification, persistence).
- **Test 11** — Sidebar settings (provider/model/key changes propagate without restart).

For each: walk through the steps, verify against the expected outcome, and update the Pass/Fail column in the guide.

Also still pending:
- A short architecture summary of the unified PLAN flow (which part is whose design, which part touches which file) — useful as a one-pager for explaining changes to teammates.
