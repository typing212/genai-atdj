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

### Dependency Map

| WP | Name | Depends On |
|---|---|---|
| WP-01 | Project Setup | — |
| WP-02 | Audio Feature Extraction & Catalog Bootstrap | WP-01 |
| WP-03 | Static UI Wireframe | WP-01 (minimal) |
| WP-04 | Basic Playback Engine | WP-01 |
| WP-05 | Tanda Validator & Energy Arc | WP-01, WP-02 |
| WP-06 | LangGraph Agent Core | WP-01, WP-02, WP-05 |
| WP-07 | ChromaDB Ingest & RAG | WP-01 |
| WP-08 | Audio Enhancement Pipeline | WP-01 |
| WP-09 | Cortina Generation & Selection | WP-01 |
| WP-10 | Full UI Integration | WP-03, WP-04, WP-06, WP-07 (core); WP-08, WP-09 (nice-to-have) |
| WP-11 | Evaluation & Demo Prep | WP-10 |

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
**Deliverable:** `atdj/audio/features.py` and `atdj/audio/metadata.py` modules complete; `catalog.csv` fully populated with real metadata and extracted features for ~50 tango tracks; cortinas routed to `data/cortinas/`

**Est. Effort:** ~10 hrs (without AI: 2–3×) · Week 1 (3/22–3/28)

**Depends on:** WP-01

**Proof of Concept Test** (`notebooks/02_audio_features.ipynb`): run `read_metadata()` + `extract_features()` on 3 sample tracks from `data/raw/`, print all fields, plot a BPM/energy bar chart. Confirm metadata fields are populated and feature values are in plausible ranges (BPM 50–200, energy 0–1) before running batch.

**Source music:** "La Fiesta De Buenos Aires" CD series (40 volumes, ~29 tracks/volume). For WP-02 PoC and catalog bootstrap, use the first ~50 tango tracks (roughly Vol-01 and Vol-02). All volumes are processed in the full batch run.

**Audio file routing (automated, no manual sorting):**
- Filename contains `"Cortina"` (case-insensitive) → `data/cortinas/` tagged `source: milonga_sequence`
- All other tracks → `data/raw/` (tango catalog)
- Backup pop cortinas (from separate `Cortina/` source folder) → `data/cortinas/` tagged `source: backup_pool`

**Metadata strategy:** Extract from MP3 ID3 tags using `mutagen`; fall back to filename parsing if tags are missing. The original Excel sequence reference may be consulted manually but the code must never depend on it.

**Detailed Tasks:**
- Implement `atdj/audio/metadata.py`:
  - `read_metadata(file_path)` — reads ID3 tags via `mutagen` (title, artist, album, track number, year); falls back to filename parsing
  - `infer_track_type(file_path)` — returns `"cortina"` if filename contains "Cortina", else `"tango"`
  - `route_files(source_dir, raw_dir, cortinas_dir)` — copies files to correct destination based on `infer_track_type()`
- Implement `AudioFeatures` dataclass in `atdj/audio/features.py`
- Implement `extract_features(file_path, track_id)` using librosa:
  - `librosa.beat.beat_track()` → bpm
  - `librosa.feature.rms()` → energy
  - `librosa.feature.spectral_centroid()` → brightness
  - `librosa.feature.chroma_cqt()` → key (argmax of mean chroma)
  - Composite danceability = 0.5 × rhythmic_regularity + 0.5 × energy_normalized
- Implement `batch_extract()` with `joblib.Parallel`
- Run `route_files()` to populate `data/raw/` and `data/cortinas/`
- Run `batch_extract()` over all ~50 tango tracks in `data/raw/`; merge metadata + features into `data/catalog.csv`, replacing the dummy rows from WP-01

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
**Deliverable:** 10 before/after pairs demonstrating audible + measurable improvement

**Est. Effort:** ~8 hrs (without AI: 2–3×) · Week 4 (4/12–4/18)

**Depends on:** WP-01

**Proof of Concept Test** (`notebooks/08_enhancement_test.ipynb`): run the full pipeline on 1 track, plot before/after mel spectrograms side-by-side using matplotlib, play both with `IPython.display.Audio`. Confirm audible improvement and no clipping before running on all 10.

**Detailed Tasks:**
- Implement `atdj/audio/enhancement.py` — 7-stage pipeline:
  read → noise reduction → tape hiss filter → EQ → limiter → LUFS normalization → write
- Apply to 10 tracks; store in `data/processed/`; update `catalog.csv` `enhanced_file_path`
- Measure SNR before/after using spectral flatness as noise proxy

---

### WP-09: Cortina Generation & Selection
**Deliverable:** `select_cortina` tool integrated with `cortina_selector` agent node

**Est. Effort:** ~8 hrs (without AI: 2–3×) · Week 4 (4/12–4/18)

**Depends on:** WP-01

**Proof of Concept Test** (`notebooks/09_cortina_generation.ipynb`): call `select_cortina_from_pool()` after a hardcoded Vals tanda, print contrast scores for each candidate, play the top-scored cortina with `IPython.display.Audio`. Confirm the selection logic prefers contrasting clips.

**Detailed Tasks:**
- Curate 10–15 non-tango clips (jazz, classical, ≥30s each) in `data/cortinas/raw/`
- Implement `atdj/audio/cortina.py`:
  - `select_cortina_from_pool()` — score by energy contrast + spectral contrast, trim with pydub
  - `generate_cortina_by_splice()` — random 2–3 clip splice with 500ms crossfade
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
| Agent plans valid milonga | 3-hour session runs without crash; every tanda passes `validate_tanda()` |
| Tanda rule compliance | ≥95% of tandas share orchestra, style, and decade |
| Orchestra repeat compliance | <5% of tandas violate the `avoid_repeat_orchestra_within=3` rule |
| Cortina placement | 100% of tanda pairs in queue are separated by a cortina |
| Feedback responsiveness | After "energy_up" event, next tanda `energy_level` > current tanda `energy_level` |
| RAG Q&A functional | 5 live demo questions return factually grounded answers in <4s |
| Audio enhancement functional | 10 enhanced tracks show SNR improvement ≥+5 dB vs raw |
| UI complete | All 4 pages load without error; session can be started and interacted with live |

### Quality Criteria

| Criterion | Target |
|---|---|
| Energy Arc RMSE | <0.10 (planned vs actual across session) |
| RAG Precision@5 | >0.80 on 20-question test set |
| Audio LUFS consistency | Std dev <1.0 LU across enhanced catalog |
| Subjective audio rating | >3.5/5.0 average on A/B listening test |
| Feedback response latency | p95 <3 seconds from event to state update |

### Reproducibility Criteria

- `uv sync` installs all dependencies from `uv.lock` with no conflicts
- `python -m atdj.rag.ingest` completes without error on any machine with catalog + audio files
- `streamlit run main.py` launches with no import errors
- `pytest tests/` passes all tests (excluding tests that require audio files, which are gated by fixture existence)
- `README.md` contains complete setup instructions a new user can follow without prior knowledge

### Media Pool Setup (Offline Preprocessing Flow)

Before launching the app, users must prepare their music pool. The expected flow is:

1. **Place source audio** — copy your music folder into a local source directory (e.g. `~/Downloads/genai_dj_musics/`)
2. **Run file routing** — execute `route_files()` from `atdj/audio/metadata.py`; this automatically sorts files into `data/raw/` (tango tracks) or `data/cortinas/` (any file with "Cortina" in the name, plus backup pool files). No manual sorting needed.
3. **Run feature extraction** — execute `batch_extract()` to populate `bpm`, `energy`, `key`, and `danceability` into `catalog.csv`. Triggered via `notebooks/02_audio_features.ipynb` or a future CLI script.
4. **Run RAG ingest** — execute `python -m atdj.rag.ingest` to index all tracks into ChromaDB
5. **Launch the app** — `streamlit run main.py`

Steps 2–4 only need to be re-run when new tracks are added. Metadata is always extracted from MP3 ID3 tags via `mutagen` — no manual spreadsheet editing required. This flow will be documented in `README.md` once all features and files are finalized.

> **Stretch goal:** See `doc/ideas.md` — User Music Upload & On-the-Fly Feature Extraction collapses steps 1–4 into a single UI action at runtime.

---

### Rubric Alignment

| Rubric Category | How Met |
|---|---|
| Demo — Live Quality (7%) | 4 distinct interactive features, all demonstrated live |
| Demo — Interactivity (6%) | Real-time feedback buttons, Q&A chat, enhancement workbench |
| Demo — Technical Depth (7%) | LangGraph state transitions visible in Agent Log; ChromaDB retrieval sources shown |
| Report — Methodology (8%) | Tanda validator rules, energy arc algorithm, RAG pipeline, enhancement stages all documented |
| Report — Results (6%) | All 5 quantitative metrics computed and visualized in `notebooks/06_evaluation.ipynb` |
| GitHub — Reproducibility (5%) | `uv sync` + `README.md` one-command setup |
| GitHub — Quality (5%) | Modular packages, type hints, tests, notebooks, clean commit history |


---

## Tech Stack

> **Status: Under Exploration** — Multiple options listed per component. Final choices to be made during WP-01. Priority: `[free/OS]` (free & open source) > `[free-tier]` (API with free quota) > `[paid]`.

---

### Runtime & Package Management

| Component | Options | Notes |
|---|---|---|
| Python | CPython 3.13 | Locked in `pyproject.toml` |
| Package manager | **uv** `[free/OS]` | Fast, lockfile-based; already in use |

---

### Agent Orchestration

| Component | Options | Notes |
|---|---|---|
| Agent framework | **LangGraph** `[free/OS]` | Best fit for cyclic stateful sessions (see rationale in blueprint) |
| | LangChain AgentExecutor `[free/OS]` | Simpler but no native cycles or shared state |
| | Pure Python + asyncio `[free/OS]` | Full control, no abstraction overhead; complex to maintain |
| LangChain core | **langchain-core** `[free/OS]` | Required for tool/message abstractions regardless of LLM choice |

---

### LLM Backbone

| Option | Cost | Notes |
|---|---|---|
| **Claude Sonnet 4.6** (`claude-sonnet-4-6`) `[paid]` | ~$3/MTok in | Strong reasoning, large context; best for complex tanda planning logic |
| Llama 3.1 / 3.3 via **Ollama** `[free/OS]` | Free, local | No API cost; needs GPU for reasonable speed; 8B sufficient for structured output |
| **Groq** (Llama 3.3 70B) `[free-tier]` | Free tier (generous) | Very fast inference; free tier may hit rate limits during dev |
| **Google Gemini 2.0 Flash** `[free-tier]` | Free tier available | Fast, large context; via `langchain-google-genai` |
| **HuggingFace Inference API** `[free-tier]` | Free tier | Many open models; latency variable |

> **Recommendation:** Use **Google Gemini** as the primary LLM — existing API credits available. Use `Gemini 2.0 Flash` for development (fast, generous free tier) via `langchain-google-genai`. Fall back to Ollama for fully offline testing. Claude Sonnet 4.6 remains an option for final demo if needed.

---

### Audio Feature Extraction

| Option | Cost | Notes |
|---|---|---|
| **librosa** `[free/OS]` | Free | BPM, key, energy, spectral features; pure Python + numpy |
| **essentia** (MTG) `[free/OS]` | Free | More music-specific features (key confidence, danceability model); heavier install |
| **madmom** `[free/OS]` | Free | State-of-the-art beat tracking; slower, less maintained |

> **Recommendation:** Start with **librosa** (easiest); add essentia if key/danceability quality is insufficient.

---

### Audio Enhancement

| Component | Options | Notes |
|---|---|---|
| Noise reduction | **noisereduce** `[free/OS]` | Spectral gating; stationary noise profile; simple API |
| | **demucs** (Meta) `[free/OS]` | Neural source separation; overkill for noise reduction but powerful |
| | **RNNoise** (via `rnnoise-python`) `[free/OS]` | Real-time-focused; less control over parameters |
| EQ / limiting / normalization | **pedalboard** (Spotify) `[free/OS]` | Professional-grade DSP chain; best all-in-one |
| | **audiomentations** `[free/OS]` | More augmentation-focused; fewer mastering tools |
| | **sox** (via `pysox`) `[free/OS]` | Battle-tested; verbose API |
| Audio I/O | **soundfile** `[free/OS]` | Fast, clean; `.flac`/`.wav` native |
| | **audioread** `[free/OS]` | Broader format support via system codecs |
| Audio manipulation | **pydub** `[free/OS]` | Trimming, crossfade, export; requires ffmpeg |

---

### RAG — Vector Store

| Option | Cost | Notes |
|---|---|---|
| **ChromaDB** `[free/OS]` | Free, local | Simple embedded DB; no server needed; good for ≤100k docs |
| **FAISS** (Meta) `[free/OS]` | Free, local | Fastest similarity search; no metadata filtering natively |
| **Qdrant** `[free/OS]` | Free, self-hosted | Rich metadata filtering; production-grade; more setup |
| **Weaviate** `[free/OS]` | Free, self-hosted | GraphQL API; complex setup |

> **Recommendation:** **ChromaDB** — lowest friction for local dev with metadata filtering needs.

---

### RAG — Embedding Model

| Option | Cost | Notes |
|---|---|---|
| **all-MiniLM-L6-v2** (sentence-transformers) `[free/OS]` | Free, local | 384-dim; fast; good general semantic similarity |
| **nomic-embed-text** (via Ollama) `[free/OS]` | Free, local | 768-dim; better retrieval quality; needs Ollama running |
| **mxbai-embed-large** (via Ollama) `[free/OS]` | Free, local | 1024-dim; state-of-the-art open embeddings |
| **text-embedding-3-small** (OpenAI) `[paid]` | ~$0.02/MTok | High quality; API cost adds up at scale |
| **Gemini text-embedding** `[free-tier]` | Free tier | Via `langchain-google-genai` |

> **Recommendation:** **all-MiniLM-L6-v2** for speed; upgrade to **nomic-embed-text** if retrieval quality is insufficient.

---

### RAG — Framework Integration

| Option | Notes |
|---|---|
| **langchain-chroma** `[free/OS]` | Tight LangChain/LangGraph integration; retriever abstraction |
| **LlamaIndex** `[free/OS]` | Alternative to LangChain for RAG; more opinionated pipeline |
| Direct ChromaDB client `[free/OS]` | Maximum control; no abstraction overhead |

---

### Data & Validation

| Component | Options | Notes |
|---|---|---|
| Data schemas | **pydantic v2** `[free/OS]` | Already decided; required for LangGraph state |
| Tabular catalog | **pandas** `[free/OS]` | Already present |
| Numerical ops | **numpy** `[free/OS]` | Already present |

---

### UI

| Option | Cost | Notes |
|---|---|---|
| **Streamlit** `[free/OS]` | Free | Fastest path to interactive demo; good for prototyping |
| **Gradio** `[free/OS]` | Free | Similar to Streamlit; better for ML demos with audio components |
| **FastAPI + React** `[free/OS]` | Free | Full control; much more development effort |

> **Recommendation:** **Streamlit** — multi-page session state and layout flexibility better serve the agentic showcase. Gradio's better audio UX is not worth sacrificing the live session console and agent log. Audio workbench is achievable with `st.audio()` + Plotly spectrograms.

---

### Visualization

| Option | Notes |
|---|---|
| **Plotly** `[free/OS]` | Interactive charts; good Streamlit integration |
| **Altair** `[free/OS]` | Declarative; lighter; less interactive |
| **Matplotlib** `[free/OS]` | Already present; static only |

---

### Dev / Infra

| Component | Choice | Notes |
|---|---|---|
| Testing | **pytest** `[free/OS]` | Standard |
| Env management | **python-dotenv** `[free/OS]` | Standard |

---

> **`pyproject.toml` dependencies will be added incrementally** as each WP is implemented and its requirements are confirmed. The current `pyproject.toml` retains only the original dependencies until then.

---

## Core Architecture

### Directory Structure

```
genai_atdj/
├── main.py                         # Streamlit entry point: streamlit run main.py
├── pyproject.toml
├── .env                            # ANTHROPIC_API_KEY (not committed)
├── .env.example
├── doc/
│   ├── Project Proposal.pdf
│   └── Project_Rubric_STATGR5293_2026.pdf
│
├── atdj/                           # Main application package
│   ├── __init__.py
│   ├── config.py                   # Paths, constants, LLM init
│   │
│   ├── schemas/                    # Pydantic models (foundation layer)
│   │   ├── track.py                # Track, TangoStyle, AudioQuality
│   │   ├── tanda.py                # Tanda (with homogeneity validator)
│   │   ├── session.py              # MilongaSession, QueueItem, Cortina
│   │   └── feedback.py             # FeedbackEvent
│   │
│   ├── audio/                      # Audio processing subsystem
│   │   ├── metadata.py             # read_metadata(), infer_track_type(), route_files()
│   │   ├── features.py             # AudioFeatures dataclass + extract_features() + batch_extract()
│   │   ├── enhancement.py          # enhance_track() pipeline
│   │   └── cortina.py              # select_cortina_from_pool(), generate_cortina_by_splice()
│   │
│   ├── rag/                        # ChromaDB + retrieval subsystem
│   │   ├── ingest.py               # build_track_document(), ingest_catalog()
│   │   ├── store.py                # PersistentClient initialization, collection handles
│   │   └── query.py                # retrieve_tracks(), answer_question(), search_for_planning()
│   │
│   ├── tanda/                      # Domain logic subsystem
│   │   ├── validator.py            # validate_tanda() — all milonga rules
│   │   ├── planner.py              # Rule-based tanda construction helpers
│   │   └── energy.py               # build_arc(), adjust_arc()
│   │
│   ├── agent/                      # LangGraph agent
│   │   ├── state.py                # AgentState TypedDict
│   │   ├── tools.py                # All @tool definitions
│   │   ├── nodes.py                # Node functions (async)
│   │   ├── edges.py                # Conditional routing functions
│   │   └── graph.py                # build_graph() → compiled StateGraph
│   │
│   └── ui/                         # Streamlit pages
│       ├── app.py                  # st.navigation() multipage setup
│       ├── page_session.py         # Live DJ console (main page)
│       ├── page_catalog.py         # Track catalog browser
│       ├── page_qa.py              # RAG Q&A chat interface
│       ├── page_audio.py           # Audio enhancement workbench
│       └── page_settings.py        # LLM API key input + runtime config
│
├── data/
│   ├── catalog.csv                 # Master track metadata + extracted features
│   ├── raw/                        # Original audio files (.mp3/.flac)
│   ├── processed/                  # Enhanced audio output
│   ├── cortinas/                   # Curated + generated cortina clips
│   ├── domain_knowledge/           # failover .md files: orchestra bios, era descriptions (primary = runtime web fetch)
│   ├── chroma_db/                  # Persisted ChromaDB on disk
│   └── sessions/                   # Session summary .md files (generated)
│
├── notebooks/
│   ├── 01_eda_catalog.ipynb
│   ├── 02_audio_feature_exploration.ipynb
│   ├── 03_tanda_planning_prototype.ipynb
│   ├── 04_rag_prototype.ipynb
│   ├── 05_cortina_generation.ipynb
│   └── 06_evaluation.ipynb
│
└── tests/
    ├── test_schemas.py
    ├── test_validator.py
    ├── test_agent.py
    └── test_rag.py
```

### Module Data Flow

```
DATA SOURCES
  data/raw/*.mp3|flac     data/catalog.csv    User via Streamlit
         │                      │                      │
         ▼                      ▼                      ▼
  atdj/audio/           atdj/rag/             atdj/ui/
  features.py   ──►     ingest.py  ──►        page_session.py
  enhancement.py        store.py              page_catalog.py
  cortina.py            query.py              page_qa.py
         │                  │                page_audio.py
         │                  │                      │
         └──────────────────┴──────────────────────┘
                            │
                     atdj/schemas/
                 Track, Tanda, MilongaSession, FeedbackEvent
                            │
                     atdj/tanda/
                 validator.py, energy.py
                            │
                     atdj/agent/
                 state.py → nodes.py → tools.py → edges.py → graph.py
                            │
                    LangGraph StateGraph
                 (session_init → tanda_planner →
                  cortina_selector → queue_publisher
                  ↕ feedback_handler → session_summary)
```

### LangGraph Node Flow

```
[START]
   │
   ▼
session_init          Load catalog, build MilongaSession, compute energy arc
   │
   ▼
tanda_planner ◄─────────────────────────────────────────────┐
   │  tools: search_catalog, validate_tanda, get_energy_target│
   │  (retry loop up to 3x on invalid tanda)                  │
   │                                                          │
   │  *** Feedback can interrupt here at any time ***         │
   │  On interrupt:                                           │
   │    - if plan B exists in lookahead → use as placeholder  │
   │    - if no plan B → finish current plan as placeholder   │
   │    - always start replan from scratch immediately        │
   │    - race replan vs. playback deadline:                  │
   │        replan wins → play replan                         │
   │        too slow   → play placeholder                     │
   │                                                          │
   ▼ (needs_cortina=True)                                     │
cortina_selector      tools: select_cortina, generate_cortina │
   │                                                          │
   ▼                                                          │
queue_publisher       Emit tanda+cortina to UI queue          │
                      Notify UI: "Next tanda updated"         │
   │                  User can click "Play Next" immediately  │
   │                                                          │
   ├─── session_complete? ──► session_summary ──► [END]       │
   │                                                          │
   └─── else ──────────────────────────────────────────────── ┘
                                                        (loop)

feedback_handler (async, event-driven — not a sequential node)
   Triggered any time by UI event (energy_up, energy_down,
   skip_tanda, floor_full, floor_empty, qa_query)
   tools: query_rag, adjust_energy_arc, skip_current_tanda
   → interrupts tanda_planner if currently running
   → posts FeedbackEvent to AgentState.pending_feedback
   → triggers replan race (see above)
   → pushes notification to UI immediately
```

---

## Data Schema

> **Draft** — schemas below are a starting point only. Field names, validation rules, and constraints will be discussed and finalized when we implement each corresponding work package.

### `atdj/schemas/track.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class TangoStyle(str, Enum):
    TANGO   = "tango"
    VALS    = "vals"
    MILONGA = "milonga"
    CORTINA = "cortina"       # non-tango break music

class AudioQuality(str, Enum):
    RAW      = "raw"
    ENHANCED = "enhanced"

class Track(BaseModel):
    id: str                               # e.g. "disarli_1942_bahia_blanca"
    title: str
    orchestra: str
    singer: Optional[str] = None          # None = instrumental
    style: TangoStyle
    year: int = Field(ge=1920, le=2030)
    decade: int                           # year // 10 * 10
    duration_seconds: float = Field(gt=0)
    file_path: str
    audio_quality: AudioQuality = AudioQuality.RAW
    enhanced_file_path: Optional[str] = None

    # Audio features — populated by atdj/audio/features.py
    bpm: Optional[float] = None
    key: Optional[str] = None             # e.g. "A minor"
    energy: Optional[float] = None        # 0.0–1.0 RMS-normalized
    danceability: Optional[float] = None  # composite score 0.0–1.0
    brightness: Optional[float] = None    # spectral centroid normalized
    snr_estimate_db: Optional[float] = None
    embedding_id: Optional[str] = None    # ChromaDB document ID

    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    model_config = {"use_enum_values": True}
```

### `atdj/schemas/tanda.py`

```python
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from atdj.schemas.track import Track, TangoStyle

class Tanda(BaseModel):
    id: str                               # uuid4
    tracks: list[Track] = Field(min_length=3, max_length=4)
    style: TangoStyle
    orchestra: str
    era_decade: int
    total_duration_seconds: float = 0.0
    energy_level: float = Field(ge=0.0, le=1.0)
    position_in_session: Optional[int] = None
    generated_by: str = "agent"           # "agent" | "manual"
    rationale: Optional[str] = None       # LLM explanation

    @model_validator(mode="after")
    def validate_homogeneity(self) -> "Tanda":
        orchestras = {t.orchestra for t in self.tracks}
        styles     = {t.style    for t in self.tracks}
        decades    = {t.decade   for t in self.tracks}
        if len(orchestras) > 1:
            raise ValueError(f"All tracks must share one orchestra: {orchestras}")
        if len(styles) > 1:
            raise ValueError(f"All tracks must share one style: {styles}")
        if len(decades) > 1:
            raise ValueError(f"All tracks must share one decade: {decades}")
        self.total_duration_seconds = sum(t.duration_seconds for t in self.tracks)
        return self
```

### `atdj/schemas/session.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, Union
from datetime import datetime
from atdj.schemas.tanda import Tanda

class Cortina(BaseModel):
    id: str
    file_path: str
    duration_seconds: float = Field(ge=10.0, le=35.0)
    source: str                           # "generated" | "curated" | "selected"
    preceding_tanda_id: Optional[str] = None
    features: dict[str, float] = Field(default_factory=dict)

class QueueItem(BaseModel):
    item_type: str                        # "tanda" | "cortina"
    content: Union[Tanda, Cortina]
    scheduled_position: int
    played: bool = False
    played_at: Optional[datetime] = None

class MilongaSession(BaseModel):
    id: str
    name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    target_duration_minutes: int = Field(default=180, ge=60, le=300)
    queue: list[QueueItem] = Field(default_factory=list)
    current_position: int = 0
    energy_arc: list[float] = Field(default_factory=list)
    actual_energies: list[float] = Field(default_factory=list)
    available_track_ids: list[str] = Field(default_factory=list)
    styles_ratio: dict[str, float] = Field(
        default_factory=lambda: {"tango": 0.70, "vals": 0.20, "milonga": 0.10}
    )
    preferred_orchestras: list[str] = Field(default_factory=list)
    avoid_repeat_orchestra_within: int = 3    # tandas
```

### `atdj/schemas/feedback.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class FeedbackEvent(BaseModel):
    id: str
    session_id: str
    timestamp: datetime
    event_type: Literal[
        "energy_up", "energy_down", "skip_tanda",
        "repeat_orchestra", "avoid_orchestra",
        "floor_full", "floor_empty",
        "qa_query", "manual_override",
    ]
    payload: dict = Field(default_factory=dict)
    processed: bool = False
    agent_response: Optional[str] = None
```

### `data/catalog.csv` Column Schema

```
id, title, orchestra, singer, style, year, decade, duration_seconds,
file_path, tags, notes,
bpm, key, energy, danceability, brightness, snr_estimate_db,
enhanced_file_path, embedding_id
```

### ChromaDB Collections

**`tango_tracks`** — one document per Track
- Embedded text: `"{title}" by {orchestra} ({year}). Style: {style}. Singer: {singer}. Decade: {decade}s. Tags: {tags}. BPM: {bpm}. Key: {key}. Energy: {energy:.2f}.`
- Metadata filter keys: `track_id, orchestra, style, decade, year, energy, bpm, has_audio`

**`milonga_knowledge`** — domain knowledge for Q&A enrichment
- **Primary source:** fetched at runtime from Wikipedia / TodoTango.com via `atdj/rag/fetch.py`
- **Failover source:** pre-indexed `.md` files in `data/domain_knowledge/` (used when fetch fails or times out)
- 500-token chunks, 50-token overlap

---

## API/Interface Specs

### LangGraph Agent State

```python
# atdj/agent/state.py
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from atdj.schemas.session import MilongaSession
from atdj.schemas.tanda import Tanda
from atdj.schemas.feedback import FeedbackEvent

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session: MilongaSession
    upcoming_tandas: list[Tanda]          # lookahead buffer (2–3 tandas)
    pending_feedback: list[FeedbackEvent]
    needs_cortina: bool
    session_complete: bool
    feedback_pending: bool
    candidate_tracks: list[dict]          # raw ChromaDB hits
    current_tanda_draft: Optional[dict]
    last_agent_action: Optional[str]
    qa_question: Optional[str]
    qa_answer: Optional[str]
    error_message: Optional[str]
    retry_count: int
```

### Agent Tools

```python
# atdj/agent/tools.py

@tool
def search_catalog(
    style: str,                           # TangoStyle value
    energy_min: float,
    energy_max: float,
    decade: int,
    orchestra: str | None = None,
    exclude_track_ids: list[str] = [],
    limit: int = 20,
) -> list[dict]:
    """Query ChromaDB with metadata pre-filter then semantic re-rank."""

@tool
def validate_tanda(track_ids: list[str]) -> dict:
    """
    Returns {"valid": bool, "errors": list[str]}.
    Rules: same orchestra, same style, same decade, 3–4 tracks,
    no duplicates in session history.
    """

@tool
def get_energy_target(tanda_position: int, total_tandas: int) -> float:
    """Return pre-computed energy arc value for this slot (0.0–1.0)."""

@tool
def adjust_energy_arc(
    session_id: str,
    from_position: int,
    delta: float,
    signal: str,                          # "floor_full"|"floor_empty"|"manual"
) -> list[float]:
    """Recompute remaining energy arc. Returns updated float list."""

@tool
def select_cortina(
    preceding_style: str,
    preceding_energy: float,
    duration_seconds: float = 20.0,
) -> dict:
    """Select highest-contrast cortina from data/cortinas/ pool."""

@tool
def generate_cortina(
    duration_seconds: float,
    contrast_features: dict[str, float],
    seed: int | None = None,
) -> dict:
    """Splice non-tango clips with crossfade. Returns Cortina dict."""

@tool
def query_rag(question: str, n_results: int = 5) -> str:
    """Embed question → retrieve tracks + knowledge → LLM answer string."""

@tool
def skip_current_tanda(session_id: str) -> dict:
    """Mark tanda skipped, remove from upcoming_tandas, trigger replan."""
```

### Audio Processing Functions

```python
# atdj/audio/metadata.py
def read_metadata(file_path: str) -> dict: ...          # ID3 tags via mutagen, falls back to filename
def infer_track_type(file_path: str) -> str: ...        # "cortina" | "tango"
def route_files(source_dir: str, raw_dir: str, cortinas_dir: str) -> None: ...

# atdj/audio/features.py
def extract_features(file_path: str, track_id: str) -> AudioFeatures: ...
def batch_extract(catalog_df, audio_dir: str, n_jobs: int = 4) -> list[AudioFeatures]: ...

# atdj/audio/enhancement.py
def enhance_track(
    input_path: str,
    output_path: str,
    noise_reduce: bool = True,
    eq_preset: str = "tango_warmth",
    normalize_lufs: float = -14.0,
    hiss_filter_hz: float = 8000.0,
) -> dict: ...                            # returns {"input", "output", "peak_db", "lufs"}

# atdj/audio/cortina.py
def select_cortina_from_pool(
    pool_dir: str,
    preceding_tanda: Tanda,
    target_duration: float = 20.0,
) -> str: ...                             # returns file path
def generate_cortina_by_splice(
    source_clips_dir: str,
    target_duration: float,
    seed_features: dict[str, float],
) -> str: ...
```

### RAG Interface

```python
# atdj/rag/query.py
def retrieve_tracks(
    question: str,
    chroma_client,
    where_filter: dict | None = None,
    n_results: int = 5,
) -> list[Track]: ...

def answer_question(
    question: str,
    chroma_client,
    llm,
) -> str: ...

def search_for_planning(
    style: str, energy_min: float, energy_max: float,
    decade: int, orchestra: str | None, exclude_ids: list[str],
    limit: int, chroma_client,
) -> list[Track]: ...
```

### Conditional Edge Routing

```python
# atdj/agent/edges.py

def route_after_tanda_planner(state: AgentState) -> str:
    # error + retry_count < 3  → "tanda_planner"
    # needs_cortina            → "cortina_selector"
    # else                     → "queue_publisher"

def route_after_queue_publisher(state: AgentState) -> str:
    # session_complete         → "session_summary"
    # feedback_pending         → "feedback_handler"
    # else                     → "tanda_planner"

def route_after_feedback_handler(state: AgentState) -> str:
    # session_complete         → "session_summary"
    # last_agent_action == "qa_answered" → "queue_publisher"
    # else                     → "tanda_planner"
```

### Streamlit UI Layout (page summaries)

| Page | File | Key Components |
|---|---|---|
| Live DJ Console | `page_session.py` | NOW PLAYING card, UP NEXT card, Energy Arc (Plotly), Feedback buttons, Queue AgGrid table, Agent Log expander |
| Track Catalog | `page_catalog.py` | Filter bar (style/orchestra/decade/energy), AgGrid table, selected track detail panel with audio player and feature radar chart |
| Q&A Assistant | `page_qa.py` | st.chat_message thread, st.chat_input, example question pills |
| Audio Workbench | `page_audio.py` | Track selector, Before/After waveform + mel spectrogram comparison, enhancement controls, Play buttons |
| Settings | `page_settings.py` | LLM provider selector, API key text input (stored in `st.session_state` only, never persisted), agent re-init on key change |

---
