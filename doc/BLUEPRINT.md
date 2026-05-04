# AT-DJ: Agentic Tango DJ — Project Blueprint & Implementation Plan

> **Living Document** — Everything in this blueprint is a starting point, not a final spec. Architecture, schemas, module interfaces, work package scope, and tech choices are all subject to change as we implement each work package and learn more. Treat every section as a working draft: we discuss, refine, and lock down details when we get there.

---

## Project Overview

**Problem:** Traditional Argentine Tango events (Milongas) follow rigid structural rules — songs are grouped into *tandas* (3–4 tracks of the same style/orchestra/era), separated by *cortinas* (15–30s non-tango breaks). Human DJs must simultaneously maintain structural compliance, read crowd energy, and manage a large catalog. Existing AI DJ solutions are either static playlists or general-purpose systems with no cultural awareness.

**Solution:** AT-DJ is a LangGraph-based agentic system that:
1. Plans valid tandas and cortinas for a full milonga session
2. Adapts dynamically to live feedback signals (energy, crowd density, skip)
3. Enhances historical tango audio quality (noise reduction, EQ)
4. Answers natural-language queries about the track catalog via RAG
5. Generates or intelligently selects cortinas contrasting each preceding tanda

**Outcome:** A live-demoed Streamlit app where a user can start a milonga session, give feedback, ask questions, and hear the agent adapt — demonstrating all four GenAI capabilities interactively.

---

## Step-by-Step Implementation Roadmap

> **Ground rules**
> - Every WP includes an **Proof of Concept Test** — a small notebook to validate the core idea before building the full module. Small, fast, no scaling required.
> - All WPs are starting-point estimates. Scope adjusts as we implement and learn.
> - Budget: **5 weeks (3/22–4/25), 3 team members, ~3–5 hrs/person/week ≈ 45–75 total hrs.** Buffer week 4/26–5/3 for polish, demo, and submission (DDL May 3).
> - WPs can be parallelized across team members where dependencies allow (see table below).

---

### Dependency Map and Status (as of 2026-05-03)

| WP | Name | Depends On | Status |
|---|---|---|---|
| WP-01 | Project Setup | — | Done |
| WP-02 | Audio Feature Extraction & Catalog Bootstrap | WP-01 | Done (librosa pipeline; essentia is out of scope on Windows — see WP-02 below) |
| WP-03 | Static UI Wireframe | WP-01 (minimal) | Done |
| WP-04 | Basic Playback Engine | WP-01 | Done |
| WP-05 | Tanda Validator & Energy Arc | WP-01, WP-02 | Done (style homogeneity at the schema layer; orchestra/decade homogeneity left as soft rules — see `doc/future_work.md` §4 for the deferred convention vs flexible mode) |
| WP-06 | LangGraph Agent Core | WP-01, WP-02, WP-05 | Done (PLAN, ADJUST_AUDIO, Q&A subgraphs all wired) |
| WP-07 | ChromaDB Ingest & RAG | WP-01 | Done |
| WP-08 | Audio Enhancement Pipeline | WP-01 | Done — extended with the chat-driven ADJUST_AUDIO subgraph in `atdj/audio/adjustment_graph.py` |
| WP-09 | Cortina Generation & Selection | WP-01 | Selection: Done (backup pool). Generation: In progress. |
| WP-10 | Full UI Integration | WP-03, WP-04, WP-06, WP-07 (core); WP-08, WP-09 (nice-to-have) | Done |
| WP-11 | Evaluation & Demo Prep | WP-10 | In progress (5-min demo script and methodology draft tracked in `doc/todo.md`) |

---

### Suggested Timeline

> Parallelized by person. Adjust based on actual team member strengths. DDL: **May 3** (demo + presentation + paper all due).

| Week | Dates | WPs Completed | Person A | Person B | Person C |
|---|---|---|---|---|---|
| 1 | 3/22–3/28 | WP-01, WP-02, WP-03 (in progress) | WP-01 setup + WP-02 extraction | WP-01 schemas + config | WP-03 UI wireframe |
| 2 | 3/29–4/4 | WP-03, WP-04, WP-05 | WP-05 validator + energy arc | WP-05 validator + energy arc | WP-04 basic playback |
| 3 | 4/5–4/11 | WP-06, WP-07 | WP-06 agent (state + graph) | WP-06 agent (tools + nodes) | WP-07 RAG + ChromaDB |
| 4 | 4/12–4/18 | WP-08, WP-09, WP-10 (in progress) | WP-08 audio enhancement | WP-09 cortina | WP-10 integration starts |
| 5 | 4/19–4/25 | WP-10, WP-11 (in progress) | WP-10 polish + report: intro & architecture | WP-11 evaluation + report: evaluation & conclusion | WP-11 report: RAG & audio + results & metrics + demo script |
| Buffer | 4/26–5/3 | WP-11 ✓ · Submission | Slides: intro + architecture + demo slides | Slides: evaluation + results + conclusion | Slides: features walkthrough + record backup demo + final submission |

---

### WP-01: Project Setup
**Deliverable:** Importable schemas, `config.py`, full directory structure, dummy `catalog.csv` for testing, test suite skeleton passing

**Est. Effort:** ~8 hrs (without AI: 2–3×) · Week 1 (3/22–3/28)

**Depends on:** —

**Proof of Concept Test** (`notebooks/01_project_setup.ipynb`): load 5 dummy rows from `catalog.csv`, instantiate `Track` schema for each, assert a valid row passes and an intentionally broken row raises a validation error.

**Detailed Tasks:**
- Create full directory structure (`atdj/`, `data/`, `notebooks/`, `tests/`)
- Write `atdj/config.py` — paths, LLM initialization
- Implement all four Pydantic schemas in `atdj/schemas/`
- Create `data/catalog.csv` with dummy/empty rows (headers + ~5 placeholder rows) for schema testing:
  columns: `id, title, orchestra, singer, style, year, decade, duration_seconds, file_path, tags, notes, bpm, energy, key, danceability`
- Write `tests/test_schemas.py` — instantiate valid and invalid Track/Tanda using dummy data, assert validators fire

---

### WP-02: Audio Feature Extraction & Catalog Bootstrap

**Deliverable:** `catalog.csv` fully populated with real metadata and extracted features for ~950 tracks (tango + cortinas); `atdj/audio/features.py` and `atdj/audio/metadata.py` production modules ready for future incremental use.

**Est. Effort:** ~10 hrs (without AI: 2–3x) · Week 1 (3/22–3/28)

**Depends on:** WP-01

**Music pool:** "La Fiesta De Buenos Aires" CD series (~40 volumes). Tango tracks go into `data/raw/`, cortinas into `data/cortinas/`.

**Feature extraction approach (decided):** **librosa** is the chosen library. essentia was explored but has no Windows wheel and is out of scope; trade-off documented in `doc/knowledge/librosa_vs_essentia.md`. Cortinas go through the same extraction but most metadata columns (orchestra, singer, year) are naturally null; style is auto-set from the folder, not filename heuristics.

**Detailed Tasks:**
- PoC exploration in `notebooks/02_audio_features.ipynb` — validate metadata + feature extraction on 3 sample tracks.
- Scale to all ~950 tracks via `joblib.Parallel` in the same notebook to build the base dataframe.
- One-time TodoTango backfill in the notebook: merge enrichment data to fill missing style / decade.
- Export finalized `catalog.csv`.
- Port the proven logic into `atdj/audio/metadata.py` (`read_metadata()`) and `atdj/audio/features.py` (`AudioFeatures` + `extract_features()` + `batch_extract()`).
- (Optional) sanity-check tests for the production modules.
---

### WP-03: Static UI Wireframe
**Deliverable:** Full Streamlit app with all pages, buttons, and interaction flows — no real backend, all responses are hardcoded stubs. Purpose: establish the visual and interaction design before any backend exists.

**Est. Effort:** ~10 hrs (without AI: 2–3×) · Weeks 1–2 (3/22–4/4)

**Depends on:** WP-01 (minimal — just folder structure)

**Proof of Concept Test:** Run `streamlit run main.py` and manually click through every page and button. Confirm zero crashes, correct navigation, and all stubs respond visibly.

**Detailed Tasks:**
- Implement `atdj/ui/app.py` — `st.navigation()` with all five pages
- `page_session.py`: session config sidebar, NOW PLAYING + UP NEXT cards (hardcoded), feedback buttons (show toast only), energy arc chart (dummy data), agent log (static placeholder text)
- `page_qa.py`: chat UI with example pills, hardcoded answer stub
- `page_catalog.py`: filter widgets, table from `catalog.csv` (or 5-row dummy), track detail panel
- `page_audio.py`: file picker, before/after spectrogram panels (static images ok), enhancement button (no-op)
- `page_settings.py`: provider selector, API key input, save button (`st.session_state` only)
- Every button must respond (toast, state change, or nav) — no dead UI
- Update `main.py` to call `atdj/ui/app.py`

**UI design principle:** Minimal and elegant — Notion/Claude-inspired. No redundant elements,
generous whitespace, one accent color (`#8B1A1A`, deep burgundy), card layouts with
`1px #EBEBEB` borders, system-ui font stack. Hide all Streamlit chrome decorations.

---

### WP-04: Basic Playback Engine
**Deliverable:** Given a hardcoded ordered list of track file paths, the app plays them in sequence with Next/Skip controls.

**Est. Effort:** ~6 hrs (without AI: 2–3×) · Week 2 (3/29–4/4)

**Depends on:** WP-01

**Proof of Concept Test** (`notebooks/04_playback_test.ipynb`): instantiate `PlaybackQueue` with 3 hardcoded file paths, call `next_track()` twice, assert current index and returned file path are correct at each step.

**Detailed Tasks:**
- Implement `atdj/playback/player.py`:
  - `PlaybackQueue` — ordered list of file paths + current index
  - `current_track()`, `next_track()`, `skip()` methods
- Wire into `page_session.py` — replace the NOW PLAYING stub from WP-03 with a real `st.audio()` component driven by `PlaybackQueue`
- Hardcoded test list: 3–5 real audio files from `data/raw/`, fixed sequence, no agent planning yet
- Persist `st.session_state.queue` across Streamlit reruns

---

### WP-05: Tanda Validator & Energy Arc
**Deliverable:** `validate_tanda` and `get_energy_target` tools reliable; tested

**Est. Effort:** ~10 hrs (without AI: 2–3×) · Week 2 (3/29–4/4)

**Depends on:** WP-01, WP-02

**Proof of Concept Test** (`notebooks/05_tanda_validator.ipynb`): manually build 3 valid and 2 invalid tandas using ~20 hardcoded track dicts, call `validate_tanda()` on each, confirm correct pass/fail. Then call `build_arc(10)` and `adjust_arc()`, plot the arc before and after adjustment.

**Detailed Tasks:**
- Implement `atdj/tanda/validator.py`:
  - `validate_tanda(track_ids, session_history)` — checks all milonga rules
  - `get_recent_orchestras(session, n)` → list for repeat checking
- Implement `atdj/tanda/energy.py`:
  - `build_arc(total_tandas)` → smooth energy curve (ramp 40% / peak 20% / wind-down 40%)
  - `adjust_arc(current_arc, from_pos, delta)` → smoothly shift remaining values
- Implement `atdj/planner/tanda_rules.py` — soft homogeneity checks for orchestra, singer, and decade (moved out of Pydantic schema intentionally):
  - **convention mode**: treat violations as hard errors
  - **flexible mode**: allow violations only if `Tanda.rationale` is non-empty
- Write `tests/test_validator.py`:
  - Valid tandas pass in both modes
  - Mixed orchestra/singer/decade raises in convention mode, passes with rationale in flexible mode
  - Style violations always raise (schema-level, not tested here)

---

### WP-06: LangGraph Agent Core
**Deliverable:** Agent plans a 6-tanda mini-session without UI, results logged to stdout

**Est. Effort:** ~18 hrs (without AI: 2–3×) · Week 3 (4/5–4/11)

**Depends on:** WP-01, WP-02, WP-05

**Proof of Concept Test** (`notebooks/06_agent_prototype.ipynb`): invoke `build_graph()` with a 30-min session config (3 tandas), print the planned queue to stdout. No UI. Confirm the graph runs end-to-end, state transitions correctly, and the output is a valid 3-tanda sequence.

**Detailed Tasks:**
- Implement `atdj/agent/state.py` — `AgentState` TypedDict
- Implement all tools in `atdj/agent/tools.py` (wire to `rag/query`, `tanda/validator`, `tanda/energy`)
- Implement all node functions in `atdj/agent/nodes.py`:
  `session_init`, `tanda_planner`, `cortina_selector`, `queue_publisher`, `feedback_handler`, `session_summary`
- Implement `atdj/agent/edges.py` — routing functions
- Implement `atdj/agent/graph.py` — `build_graph()` returning compiled `StateGraph`
- Write `tests/test_agent.py` — mock LLM responses, assert state transitions correct

---

### WP-07: ChromaDB Ingest & RAG Query Layer
**Deliverable:** `query_rag` tool works end-to-end; Q&A page can be wired up

**Est. Effort:** ~10 hrs (without AI: 2–3×) · Week 3 (4/5–4/11)

**Depends on:** WP-01

**Proof of Concept Test** (`notebooks/07_rag_prototype.ipynb`): ingest 10 tracks + 3 knowledge docs (1 fetched live, 2 from local failover) into a local ChromaDB instance, run 5 test questions, print retrieved chunks + LLM answer. Confirm retrieval is semantically relevant before wiring to agent tools.

**Knowledge retrieval design:**
- **Primary:** fetch domain knowledge at runtime from trusted web sources (Wikipedia, TodoTango.com) via a `fetch_knowledge()` function — always attempted first
- **Failover:** if fetch fails or times out, fall back to curated `.md` files in `data/domain_knowledge/` (orchestra bios, era descriptions) — these are never the primary source, only the safety net
- Fetched content is chunked and temporarily indexed into ChromaDB for the session; failover docs are pre-indexed at ingest time

**Detailed Tasks:**
- Implement `atdj/rag/store.py` — `get_client()`, `get_or_create_collection()`
- Implement `atdj/rag/ingest.py` — `build_track_document()`, `ingest_catalog()`, `ingest_knowledge_docs()`
- Implement `atdj/rag/fetch.py` — `fetch_knowledge(query)`: attempts live web fetch (Wikipedia API / TodoTango), returns text; falls back to local `data/domain_knowledge/` `.md` files on failure
- Add 3–5 failover `.md` files to `data/domain_knowledge/` covering the most common orchestras (Di Sarli, Troilo, D'Arienzo, Canaro, Pugliese)
- Run full ingest; verify `tango_tracks` and `milonga_knowledge` collections populated
- Implement `atdj/rag/query.py` — all three query functions

---

### WP-08: Audio Enhancement Pipeline
**Deliverable:** 10 before/after pairs demonstrating audible + measurable improvement.

**Est. Effort:** ~8 hrs (without AI: 2–3×) · Week 4 (4/12–4/18)

**Depends on:** WP-01

**Proof of Concept Test** (`notebooks/08_enhancement_test.ipynb`): run the full pipeline on 1 track, plot before/after mel spectrograms side-by-side, play both with `IPython.display.Audio`. Confirm audible improvement and no clipping before running on all 10.

**Pipeline (high level):** Six stages applied in fixed order — noise reduction → highpass + low-shelf + peak EQ → LUFS normalization → limiter → dynamic hiss filter → write WAV. Three parameters are computed per track (noise strength, EQ gains, hiss cutoff) by comparing each track's SNR and spectral centroid against the tanda median, so a tanda's tracks end up sounding consistent without any one losing its character. Fixed parameters (rumble highpass at 80 Hz, target -14 LUFS, limiter ceiling at -1 dBFS) come from physics and playback standards. The design philosophy is subtle correction, not aggressive transformation — enhancement should be inaudible as "processing", the listener just notices the tanda sounds clean and consistent.

**Pass criteria:** mean SNR improvement ≥ +5 dB across the batch; LUFS standard deviation < 1.0 LU within a tanda.

**Detailed Tasks:**
- Implement `atdj/audio/enhancement.py` — six-stage pipeline + per-track adaptive parameter computation.
- Apply to 10 tracks; store enhanced WAVs in `data/processed/`; update `catalog.csv` `enhanced_file_path`.
- Measure SNR before/after; record results in the PoC notebook.
- Future hook: expose `enhance_track()` as a LangGraph tool so the agent can drive it with tanda-aware parameters (lands as part of WP-06).

---

### WP-09: Cortina Generation & Selection
**Deliverable:** `select_cortina` and `generate_cortina` tools integrated with the `cortina_selector` agent node.

**Est. Effort:** ~8 hrs (without AI: 2–3×) · Week 4 (4/12–4/18)

**Depends on:** WP-01

**Cortina pool design:**
- **Backup pool:** all pre-existing music in `data/cortinas/` — files labeled "Cortina" in the filename and non-tango pop/jazz clips are all treated equally as backup cortinas.
- **Generated:** purpose-built transition clips (short, neutral, designed for milonga use) that supplement the backup pool.

**Proof of Concept Test** (`notebooks/09_cortina_selection.ipynb`): call `select_cortina_from_pool()` after a hardcoded Vals tanda, print contrast scores for each candidate, play the top-scored cortina with `IPython.display.Audio`. Confirm the selection logic prefers contrasting clips.

**Detailed Tasks:**
- Implement `atdj/audio/cortina.py`:
  - `select_cortina_from_pool()` — score clips in `data/cortinas/` by energy contrast + spectral contrast vs. preceding tanda, trim to 20–30s with pydub
  - `generate_cortina_by_splice()` — splice 2–3 non-tango clips with 500ms crossfade to produce a fresh transition clip
- Wire `select_cortina` and `generate_cortina` tools in `atdj/agent/tools.py`

---

### WP-10: Full UI Integration
**Deliverable:** Full end-to-end demo runnable with `streamlit run main.py`

**Est. Effort:** ~14 hrs (without AI: 2–3×) · Weeks 4–5 (4/12–4/25)

**Depends on:** WP-02, WP-03, WP-06, WP-07 (core); WP-08, WP-09 (nice-to-have)

**Proof of Concept Test:** Run the WP-03 static wireframe end-to-end before touching any real backend — confirm zero nav/state bugs as the baseline before integrating live functions.

**Detailed Tasks:**
- Replace all WP-03 stubs with real function calls, one page at a time
- `page_session.py`: wire to `build_graph().astream()` via `asyncio`; hook feedback buttons to `FeedbackEvent`; connect `PlaybackQueue` from WP-04
- `page_qa.py`: wire to `answer_question()` RAG tool
- `page_catalog.py`: wire filters to real `catalog.csv` query + feature radar chart
- `page_audio.py`: wire to `enhance_track()` + real before/after spectrograms
- `page_settings.py`: wire API key to runtime injection in `atdj/config.py`; re-init agent on key change

---

### WP-11: Evaluation, Report & Presentation
**Deliverable:** All metrics computed; full report drafted; slides complete; live demo ready; repo submitted

**Est. Effort:** ~18 hrs (without AI: 2–3×) · Weeks 5 + Buffer (4/19–5/3)

**Depends on:** WP-10

**Proof of Concept Test:** N/A — evaluation runs on a completed, integrated system.

**Detailed Tasks:**

*Evaluation (all):*
- Run 3 simulated 180-min sessions; compute automated metrics (rule compliance, replan latency, energy arc RMSE)
- Ablation: agent vs random selection — compare rule compliance rate
- Subjective A/B audio enhancement rating (3 raters, 10 pairs, 5-point Likert)
- RAG evaluation: 20 test questions, manual relevance labels → Precision@5

*Report writing (split by person):*
- Person A: Introduction, motivation, problem statement, system architecture section
- Person B: Evaluation methodology, ablation analysis, conclusion
- Person C: RAG design & implementation, audio enhancement design & implementation, results & metrics visualization

*Presentation slides (split by person):*
- Person A: Intro + system architecture slides + live demo slides (counts as demo prep)
- Person B: Evaluation + results + conclusion slides
- Person C: Feature walkthrough slides (RAG, audio, cortina) + record backup demo video

*Shared final tasks:*
- Write `README.md` with setup + run instructions
- Final code pass: remove debug prints, verify type hints, `uv lock` and commit
- Submission

---

## Definition of Done

### Functional Criteria

| Criterion | Pass Condition |
|---|---|
| Agent plans a multi-tanda session | A multi-tanda PLAN runs without crash; cortinas are inserted between tandas; if no tracks match a tanda prompt, a warning is logged and that tanda is skipped (no fabricated tracks). |
| Tanda style homogeneity | Pydantic schema enforces single style per tanda (no mixing tango / vals / milonga). |
| Cortina placement | Every tanda pair in the published queue is separated by a cortina. |
| RAG Q&A functional | Tango knowledge questions return grounded answers via local-knowledge-first → Wikipedia fallback retrieval. |
| Audio enhancement functional | Pipeline produces an enhanced WAV with SNR improvement ≥ +5 dB over raw on the test signal (verified by `tests/test_audio_enhancement/test_enhancement.py`). |
| Chat-driven audio adjustment | Cover the ten ADJUST_AUDIO scenarios documented in the methodology (happy path, clarification, cancel, current-track read-only menu, no-targets, reset, off-topic interrupt, free-form non-option reply, unsupported feature, fallback on missing file). |
| UI complete | Single Streamlit page loads cleanly with all panels visible (Now Playing, Energy Arc, Full Playlist, Chat, Session Log, Search) and the chat classifier routes correctly into PLAN / ADJUST_AUDIO / Q&A. |

### Quality Criteria

| Criterion | Target |
|---|---|
| Audio LUFS landing | Each enhanced track lands within ±6 LU of the −14 LUFS target (`tests/test_audio_enhancement/test_enhancement.py::test_lufs_near_target`). |
| Test suite | ~399 tests collected; the pure-logic subset passes without an LLM API key. |
| PLAN latency | A single-tanda PLAN completes in under ~10s on Claude with a warm cache (per `tests/UI_TEST_GUIDE.md`). |
| ADJUST_AUDIO latency | First-turn routing + parsing in under ~20s on Claude; subsequent menu-pick turns in under ~12s. |
| Q&A latency | Tango-knowledge questions in under ~20s on Claude (Gemini path is markedly slower and is documented as such). |

### Reproducibility Criteria

- `uv sync` installs all dependencies from `uv.lock` with no conflicts.
- `python -m atdj.rag.ingest` completes without error on any machine with the catalog + audio files in place.
- `streamlit run main.py` launches with no import errors (~399 tests also collect without import-time failure).
- `pytest tests/ -m "not integration"` passes the offline subset; integration tests run with an Anthropic or Gemini key in `.env`.
- `README.md` contains complete setup instructions a new user can follow without prior knowledge.

---

### Rubric Alignment

Mapped to the official rubric in `doc/course/Project_Rubric_STATGR5293_2026.pdf`. The Category column states what the rubric requires; the How Met column states what we deliver to satisfy it.

| Category | How Met |
|---|---|
| **Project Proposal — Clarity of Objectives (4%)** | Three-mode tango-DJ assistant (PLAN, ADJUST_AUDIO, Q&A); scope mirrored in BLUEPRINT and README. |
| **Project Proposal — Feasibility (3%)** | 5-week / 3-person timeline with deferred items listed in `doc/future_work.md`; essentia blocker mitigated by librosa. |
| **Project Proposal — Innovation and Relevance (3%)** | Chat-driven audio adjustment with current-track read-only enforcement; ten enumerated corner cases. |
| **Presentation — Problem Statement (10%)** | Framing in methodology §1–§2; ready for slides. |
| **Presentation — Major Contributions (10%)** | Audio-adjustment subgraph, router design, adaptive DSP pipeline, session log — methodology §3.3. |
| **Presentation — Evaluation (10%)** | Functional + quality criteria, latency table in `UI_TEST_GUIDE.md`, ~399-test suite. *Gap: no formal ablation or user study.* |
| **Final Report — Structure and Format (5%)** | Methodology section in; teammates own intro, evaluation, conclusion. |
| **Final Report — Depth of Research (8%)** | `doc/knowledge/` decision-log entries (LangGraph, ChromaDB, librosa vs essentia, Pydantic, Streamlit) cite-ready. |
| **Final Report — Methodology (8%)** | `doc/report/methodology.md` — top-down architecture, diagrams, ten-scenario coverage. |
| **Final Report — Results and Analysis (6%)** | Targets from quality criteria, measured numbers from tests + UI_TEST_GUIDE; pair them in the results section. |
| **Final Report — Grammar and Writing Quality (3%)** | Final pass before submission; methodology already in report-style prose. |
| **Demo — Live Demo Quality (7%)** | Latency-grounded 5-min script with fallbacks (`todo.md` Task 2). |
| **Demo — Interactivity and Engagement (6%)** | Live PLAN → ADJUST_AUDIO → Q&A walkthrough; Q&A rehearsed via spotlight scenarios. |
| **Demo — Technical Depth (7%)** | Narration ties on-screen actions to the methodology diagrams; ten-scenario coverage as talking point. |
| **GitHub — Repository Quality (5%)** | Modular `atdj/*` packages, Pydantic schemas, ~399 tests, README + BLUEPRINT + methodology + knowledge docs, clean commits. |
| **GitHub — Reproducibility (5%)** | `uv sync`, `.env.example`, documented ingest + launch, offline test subset (`-m "not integration"`). |


---
