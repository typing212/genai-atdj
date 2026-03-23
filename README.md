# AT-DJ: Agentic Tango DJ

An AI-powered DJ system for Argentine Tango milongas. It plans tanda/cortina sequences, adapts to live feedback from the dance floor, and answers natural-language questions about the music — all through a Streamlit interface.

> **Internal doc** — for teammates during development. A public-facing version will replace this after the project is complete.

---

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd genai_atdj
uv sync

# 2. Set up environment
cp .env.example .env
# Open .env and fill in your API key(s)

# 3. Download music from the shared Google Drive and place files into:
#    - data/raw/       ← tango tracks
#    - data/cortinas/  ← cortina clips
# https://drive.google.com/drive/folders/1B12Mn9hY1XV2Vutjd1TVMbfqQFrAtKqf?usp=sharing

# 4. Run tests to confirm setup works
uv run pytest tests/ -v
```

> Run the UI: `uv run streamlit run main.py` — first version of the DJ Console is live (WP-03).

---

## Environment Variables

| Variable | What it's for |
|---|---|
| `LLM_PROVIDER` | `gemini` (default) \| `claude` \| `ollama` |
| `GOOGLE_API_KEY` | Required if using Gemini |
| `ANTHROPIC_API_KEY` | Required if using Claude |
| `GEMINI_MODEL` | Default: `gemini-2.0-flash` |
| `CLAUDE_MODEL` | Default: `claude-sonnet-4-6` |

Never commit `.env` — it is gitignored. Only `.env.example` is tracked.

---

## Where to Find Things

| Resource | Where |
|---|---|
| Full project spec & task breakdown | `doc/BLUEPRINT.md` |
| Schema field reference | `atdj/schemas/README.md` |

---

## Current Status

**WP-01 complete · WP-03 first version complete · WP-02 in progress**

| WP | Name | Status |
|---|---|---|
| WP-01 | Project Setup | Done |
| WP-02 | Audio Feature Extraction & Catalog Bootstrap | In progress (Next Step) |
| WP-03 | Static UI Wireframe | First version done |
| WP-04 | Basic Playback Engine | Planned |
| WP-05 | Tanda Validator & Energy Arc | Planned |
| WP-06 | LangGraph Agent Core | Planned |
| WP-07 | ChromaDB Ingest & RAG | Planned |
| WP-08 | Audio Enhancement Pipeline | Planned |
| WP-09 | Cortina Generation & Selection | Planned |
| WP-10 | Full UI Integration | Planned |
| WP-11 | Evaluation & Demo Prep | Planned |

Full timeline and task breakdown: `doc/BLUEPRINT.md`

---

## What Was Built in WP-01

The goal of WP-01 was to set up the shared foundation everyone else's code will build on — schemas, config, folder structure, and a test suite. No audio processing yet; just dummy data.

**Schemas (`atdj/schemas/`)** — four Pydantic data models used across all modules:
- `Track` — a single audio file (title, orchestra, style, year, extracted features)
- `Tanda` — a group of 3–4 tracks played together; style must be homogeneous
- `MilongaSession` — the full session state (queue, energy arc, planning mode)
- `FeedbackEvent` — a real-time signal from a human operator during the milonga

**Config (`atdj/config.py`)** — all file paths and LLM settings in one place; reads from `.env`

**Catalog (`data/catalog.csv`)** — 5 dummy rows for testing; real rows added in WP-02

**Tests (`tests/test_schemas.py`)** — 14 tests, all passing:
```
uv run pytest tests/ -v
```

**PoC notebook (`notebooks/01_project_setup.ipynb`)** — loads dummy catalog, instantiates schemas, verifies validation works end-to-end

---

## What Was Built in WP-02 (Work In Progress)

The goal of WP-02 is to bootstrap our dataset by extracting audio features, merging them with real metadata, and generating the foundational `catalog.csv`. **This work package is currently in progress** and is our immediate next focus. 

Here is what has been built and explored so far:

**Metadata Enrichment (`notebooks/02_todotango_scraper.ipynb`)** — Scraper completed. We successfully pulled missing style and decade data from the TodoTango database to supplement our local files.
- **Output:** Scrape results are saved in `data/processed/todotango_enriched.csv` and are ready for the final catalog merge.

**Feature Extraction PoC (`notebooks/02_audio_features.ipynb`)** — The end-to-end bootstrap notebook has been mapped out, but development is currently blocked by Vanessa's Windows OS environment issues.
- **Blocker:** The `essentia` audio library is failing to run natively on Windows. We will need to decide on a workaround (e.g., using WSL, Docker, or proceeding exclusively with `librosa`).

**Instrument Extraction (`notebooks/02_instrument_Extraction.ipynb`)** — Explored dedicated instrument extraction as an additional feature, but initial results were poor and unreliable. This approach is currently shelved.

**Next Steps for WP-02:**
Resolve the Windows/Essentia blocker, finish the end-to-end extraction pipeline in the PoC notebook, generate the final ~950 track `catalog.csv`, and finally port the proven logic into the `atdj/audio/` production modules.

---

## What Was Built in WP-03

The goal of WP-03 was a fully laid-out static UI — no live agent logic yet, but all panels wired up with realistic stub data so the rest of the team can see the target interface.

**DJ Console (`atdj/ui/page_main.py`)** — single-page Streamlit app with three rows:

- **Now Playing / Playback / Energy Arc**: live track card (orchestra, singer, decade), transport controls, volume + gap settings, and an Altair energy-arc chart showing the planned session arc
- **Agent Chat / Session Log**: \an agent chat panel with style/mode selectors, and a timestamped session log
- **Full Playlist**: scrollable tanda/cortina queue with reorder (↑ ↓) and remove (×) controls; active track highlighted
- **Search Music / Upload**: search box to find and queue tracks, file uploader for new audio

Design tokens (colors, badge styles, fonts) are in `atdj/ui/DESIGN_SYSTEM.md`.

---

## Using Claude Code (AI Dev Assistant — optional)

Vanessa is using [Claude Code](https://claude.ai/claude-code) as an AI coding assistant. If you'd like to use it too, the `.claude/` folder has project-level config that loads automatically in every Claude Code session.

**Two useful slash commands you can type in Claude Code:**

`/knowledge <question>` — researches a topic and saves a summary to `doc/knowledge/`
```
/knowledge what is the difference between langgraph nodes and edges?
```

`/idea <description>` — logs a feature idea to `doc/ideas.md` after you confirm it
```
/idea add a page where the user can browse the music pool
```

**Hooks running in the background:**
- Blocks Claude from reading `.env` directly (API key protection)
- Asks for confirmation before Claude touches files outside this project folder

---

## Notes

- Do not commit real API keys. If you accidentally push them, rotate them immediately.
- `data/raw/`, `data/cortinas/`, and `data/catalog.csv` are gitignored — music files live locally only. Download the music from the [shared Google Drive](https://drive.google.com/drive/folders/1B12Mn9hY1XV2Vutjd1TVMbfqQFrAtKqf?usp=sharing) and place the tango tracks in `data/raw/` and cortinas in `data/cortinas/`.
- Read `doc/BLUEPRINT.md` before starting a new work package — it has the full task list, dependencies, and PoC notebook specs for each WP.
- **Mac/Linux teammates:** `notebooks/02_audio_features.ipynb` has an essentia section (Section 3) that is skipped on Windows. Install essentia (`uv add essentia`) and run those cells — compare BPM, key, and danceability results with the librosa cells above and add your observations to the notebook.
