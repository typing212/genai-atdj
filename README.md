# AT-DJ — Agentic Tango DJ

An AI-powered DJ assistant for Argentine Tango milongas. AT-DJ plans tanda and cortina sequences with a language-model agent, lets you adjust audio quality through chat ("a bit warmer", "softer for the next tanda"), and answers natural-language questions about the music — all from a single Streamlit interface.

> Built as a course project at Columbia (GenAI, Spring 2026). The system runs locally against your own music collection; no cloud playback.

---

## What it does

AT-DJ has three chat modes (plus a cortina generator), all routed by an LLM classifier behind a single chat box:

- **PLAN** — describe a session in plain English ("plan a relaxed Di Sarli tango tanda, then a more dramatic Pugliese tanda") and the agent picks tracks from your catalog, slots in cortinas between tandas, and publishes the playlist. A full-session prompt (e.g. "plan a full milonga session, romantic 1940s") triggers a six-slot schema (Tango Tango Vals Tango Tango Milonga) with combo-key uniqueness across the set.
- **Audio Enhancement** — adjust the sound of upcoming tracks by chat ("the next tanda is too harsh", "a bit louder", "back to default"). The agent measures the currently-playing track as a reference and applies a relative correction to the upcoming tanda. The currently-playing track itself is read-only.
- **Q&A** — ask about orchestras, singers, eras, terminology — answered through retrieval over a curated tango knowledge base plus Wikipedia fallback.
- **CORTINA generation** — between tandas, the agent either picks the best-matching clip from a backup pool or has the LLM craft a music prompt and synthesises a fresh 25-second cortina via Lyria. Pool is the deterministic safe fallback when generation fails.

Around the chat panel: a custom audio player with auto-advance and gap control, a Now Playing card, an energy-arc chart of the planned session, a structured session log, and a search panel for adding tracks manually.

---

## Quick start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- An API key for **either** Anthropic Claude **or** Google Gemini
- Your own tango music collection (MP3 / WAV) — AT-DJ runs locally against your files

### Install

```bash
git clone <repo-url>
cd genai_atdj
uv sync
```

### Configure your API key

Copy the example env file and fill in your key:

```bash
cp .env.example .env
```

Then edit `.env`:

```
ANTHROPIC_API_KEY=sk-...        # for Claude
GEMINI_API_KEY=...              # for Gemini (legacy GOOGLE_API_KEY also accepted)
CLAUDE_MODEL=claude-sonnet-4-6  # optional, has a sensible default
GEMINI_MODEL=gemini-2.0-flash   # optional, has a sensible default
```

You only need a key for the provider you intend to use; the other can be blank. You can also enter the key directly in the app sidebar at runtime, which overrides the `.env` value.

### Add your music

Place your audio files into:

- `data/raw/` — tango / vals / milonga tracks ([sample collection on Google Drive](https://drive.google.com/file/d/1MAEvcM_fsU7Gx5tTIDKvM_tkkdJnukAE/view?usp=sharing); request access if needed)
- `data/cortinas/` — short cortina clips ([sample collection on Google Drive](https://drive.google.com/file/d/1nSaDfduErWJ7CHPVYiv4mdobe8bs2XVc/view?usp=sharing); request access if needed)

These directories are gitignored — files stay local. The accompanying catalog file at `data/essentia_newsamp.csv` describes each track's metadata and audio features and is used by the playback engine.

### Build the search index (first run)

```bash
uv run python -m atdj.rag.ingest --tracks      # index the track catalog
uv run python -m atdj.rag.ingest --knowledge   # index the tango knowledge base
```

These persist to `data/chroma_db/` and only need to be rerun when the catalog or knowledge base changes.

### Launch the app

```bash
uv run streamlit run main.py
```

Open the URL Streamlit prints (typically `http://localhost:8501`). In the sidebar pick your provider, pick a model, paste your API key, and click **Save Settings**.

---

## Using AT-DJ

A typical session:

1. **Plan a tanda or two**
   - `Plan a Pugliese tango tanda from the 1940s.`
   - `Start with a relaxed Di Sarli tanda, then a more dramatic Pugliese tanda.`
   - `Build a short milonga set — three lively tracks.`
2. **Press play.** The custom audio player auto-advances through tracks and cortinas with a configurable transition gap.
3. **Adjust the sound through chat** while music is playing.
   - `Make the next tanda a bit warmer.`
   - `The current track is too loud — soften the next one.`
   - `Back to default for the rest of the session.`
   When you reference the *current* song, AT-DJ will offer a short menu (apply to the rest of the session / next tanda only / cancel) rather than touching what is already playing.
4. **Ask questions about the music** any time.
   - `Who is Carlos Di Sarli?`
   - `What characterizes Pugliese's style?`
   - `What is the difference between tango and vals?`
5. **Inspect the session log** — every agent action and every user action is timestamped and colour-coded. The full log is also saved as JSON to `data/log/`.

Manual controls (move tracks up/down, remove, add from the search panel, change transition or cortina length) are always available alongside the chat.

If you want to see our demo, you can check it out here: [Demo](https://drive.google.com/file/d/184KKkalDu6b6xZBD-Umu6_u5RX0L1VJl/view?usp=drive_link)

---

## How it works (high level)

- **UI:** Streamlit, with a custom HTML/JS audio player so playback isn't interrupted by Streamlit reruns.
- **Agent:** [LangGraph](https://github.com/langchain-ai/langgraph). One classifier routes messages into one of three subgraphs (PLAN / Audio Enhancement / Q&A). State is shared via a typed `AgentState`.
- **RAG:** [ChromaDB](https://www.trychroma.com/) over the track catalog and a curated tango knowledge base, with Wikipedia as a secondary source for Q&A.
- **Audio enhancement:** a five-stage DSP chain (noise reduction → 3-band EQ → LUFS normalization → limiter → dynamic hiss filter) implemented with `noisereduce`, `pedalboard`, and `pyloudnorm`. Per-track parameters are computed from a tanda-wide spectral and SNR analysis so tracks sound consistent as a group.
- **Schemas:** Pydantic v2 throughout (`atdj/schemas/`).
- **LLM:** Anthropic Claude or Google Gemini, selected from the sidebar at runtime.

For the engineering blueprint and tech-stack rationale, see [`doc/BLUEPRINT.md`](doc/BLUEPRINT.md).

---

## Project layout

```
atdj/
  agent/          LangGraph nodes, edges, shared state, tools
  audio/          DSP pipeline + chat-driven adjustment subgraph
  cortina/        Cortina pool fallback and Lyria-based generator
  rag/            ChromaDB ingest, retrieval, Q&A, prompt translation
  schemas/        Pydantic models (Track, Tanda, FeedbackEvent, ...)
  ui/             Streamlit pages, custom audio player, layout
  features/       Audio feature extraction (librosa pipeline)
  playback/       Cursor-managed playlist queue
  config.py       Paths and LLM factory
data/
  raw/            Your tango tracks (gitignored)
  cortinas/       Your cortina clips (gitignored)
  knowledge_base/ Curated tango markdown knowledge for RAG
  chroma_db/      Persisted vector store (built on first run)
  log/            Per-session JSON activity logs
doc/
  BLUEPRINT.md         Engineering plan, module breakdown, tech stack
  knowledge/           Decision-log entries (LangGraph vs alternatives, etc.)
  report/              Draft report sections (methodology, ...)
tests/                  ~399 tests; see tests/README.md
main.py                 App entry point
```

---

## Tests

```bash
uv run pytest tests/ -v
```

Skip integration tests (which call out to a real LLM) with `-m "not integration"`. See [`tests/README.md`](tests/README.md) for what each test file covers.

---

## Documentation

- [`doc/BLUEPRINT.md`](doc/BLUEPRINT.md) — engineering plan, module breakdown, current status, and tech-stack decisions.
- [`tests/UI_TEST_GUIDE.md`](tests/UI_TEST_GUIDE.md) — manual end-to-end test scenarios with measured latencies.
- [`atdj/schemas/README.md`](atdj/schemas/README.md) — field-by-field schema reference.
- [`doc/ai_usage.md`](doc/ai_usage.md) — disclosure of AI tool usage during the project.

---

## Authors

Built as a course project for **STAT GR5293 — GenAI Systems**, Columbia University, Spring 2026.

- **Shichen (Tina) Ma** (sm5917)
- **Yuhan (Nancy) Ma** (ym3124)
- **Nanhai (Vanessa) Zhong** (nz2448)

## License & credits

Academic project — Columbia GenAI, Spring 2026. Source code and documentation in this repository are the authors' work and may be reused for academic purposes with attribution. Music and recordings used during development remain the property of their respective rights holders; the system runs only against music you have provided yourself, and no music is shipped in this repository.
