# `atdj/rag/` — Retrieval-Augmented Generation Layer

This directory contains the full RAG subsystem for **AT-DJ**, the Agentic Tango DJ. It powers three capabilities:

1. **Semantic track search** — find tracks by natural-language description
2. **Q&A over the catalog and domain knowledge** — answer questions about tracks, orchestras, and tango history
3. **Structured retrieval for tanda planning** — filter and rank tracks so the LangGraph agent can build valid tandas

---

## Why RAG?

Argentine Tango DJing is a domain-specific, knowledge-intensive task. Two problems arise that RAG directly solves:

**The catalog problem.** The track catalog contains ~300+ recordings with rich metadata — orchestra, style (tango / vals / milonga), decade, BPM, energy, danceability, key, and audio features extracted by Essentia. A plain LLM has no access to this private data. RAG indexes the catalog into a vector database so any query — "energetic 1940s D'Arienzo tangos" — can be answered by retrieving real tracks rather than hallucinating them.

**The domain knowledge problem.** Tango has a deep cultural vocabulary (tandas, cortinas, the Golden Age orchestras, style differences between Di Sarli and D'Arienzo) that may not be well-represented in a general-purpose LLM's training data. RAG grounds answers in curated local knowledge files and live Wikipedia lookups rather than relying on model memory.

Without RAG, the agent would have to reason about tango structure using only its parametric knowledge — leading to invalid tandas, hallucinated track metadata, and unhelpful Q&A responses. With RAG, every answer is grounded in actual catalog data or retrieved text.

---

## How RAG Helps AT-DJ

| Capability | Without RAG | With RAG |
|---|---|---|
| Tanda planning | LLM guesses at track names | Agent retrieves real tracks from ChromaDB, filtered by style/decade/energy |
| Q&A (catalog) | Hallucinated BPM, year, orchestra info | Exact values looked up from the indexed catalog |
| Q&A (domain) | Generic tango trivia from training data | Answers grounded in local markdown files or live Wikipedia |
| Full-set planning | No awareness of what tracks exist | `plan_set.py` translates a natural-language prompt into a scored, deduplicated 6-slot milonga set |

---

## Architecture Overview

```
User prompt / agent query
        │
        ▼
prompt_to_features.py      ← translate natural language → feature bundle (LLM)
        │
        ▼
select_tanda.py            ← score & rank catalog tracks against feature bundle
plan_set.py                ← orchestrate 6-slot milonga set (calls select_tanda per slot)
        │
        ▼
query.py ──────────────────────────────────────────────────────────────────┐
  retrieve_tracks()         ← semantic search over tango_tracks            │
  answer_question()         ← full RAG Q&A pipeline                        │
  search_for_planning()     ← metadata-filtered retrieval for the agent    │
        │                                                                   │
        ▼                                                                   ▼
store.py                                                              fetch.py
  ChromaDB PersistentClient                                     local .md files
  "tango_tracks" collection                                     Wikipedia API
  "domain_knowledge" collection
        ▲
        │
ingest.py                  ← one-time (or reset) index build
  ingest_catalog()          ← CSV → tango_tracks
  ingest_knowledge_docs()   ← *.md → domain_knowledge
```

---

## Script Reference

### `store.py` — ChromaDB Connection Layer

**What it does:** Creates and manages the persistent ChromaDB client and the two named collections used throughout the system.

**Collections:**
- `"tango_tracks"` — one document per track in `rag_catalog.csv`, used for semantic music search
- `"domain_knowledge"` — chunked markdown files (orchestra bios, style notes, historical context), used for Q&A

**Key functions:**
- `get_client()` — returns a singleton `PersistentClient` pointed at `data/chroma_db/`. Uses a module-level singleton to avoid reloading sentence-transformers on every Streamlit rerun.
- `get_or_create_collection(name)` — idempotent collection access; cosine similarity space.

**Design note:** All other modules call `get_client()` and `get_or_create_collection()` rather than instantiating ChromaDB directly, so the DB path is a single source of truth.

---

### `ingest.py` — Index Builder

**What it does:** Populates the ChromaDB collections from local files. This is a one-time (or reset) operation, not run at query time.

**Sources ingested:**
- `data/knowledge_base/rag_catalog.csv` → `"tango_tracks"` collection. Each row becomes one embedding document with metadata fields: title, orchestra, singer, style, decade, year, BPM, energy, danceability, key, tags, and more.
- `data/knowledge_base/*.md` → `"domain_knowledge"` collection. Markdown files are split into ~400-character chunks before indexing so retrieval returns focused passages rather than entire documents.

**CLI usage:**
```bash
# Ingest only the track catalog
python -m atdj.rag.ingest --tracks --reset

# Ingest only local knowledge markdown files
python -m atdj.rag.ingest --knowledge --reset

# Ingest both (default)
python -m atdj.rag.ingest --all --reset
```

**Design note:** `ingest.py` handles only local data. Live web content (Wikipedia) is fetched at query time by `fetch.py`, not pre-indexed here.

---

### `fetch.py` — Runtime Knowledge Fetcher

**What it does:** Retrieves background text at query time to enrich the RAG prompt for Q&A. This is the "live web" layer of the three-source design.

**Source priority:**
1. **Local markdown files** in `data/knowledge_base/` — preferred when a strong local match exists (curated, trustworthy, fast)
2. **Wikipedia API** — used when local markdown doesn't match well; covers general musician/orchestra/historical background
3. **Fallback** — if both fail, returns an empty result; `query.py` may still answer using model knowledge with a clear disclaimer

**Key function:** `fetch_knowledge(query)` — takes a raw user query, normalizes it for lookup (strips question preambles like "who is", "tell me about"), tries local markdown first, then Wikipedia, and returns a structured dict with `source_type`, `source_label`, `source_url`, and `content`.

**Design note:** `fetch.py` never generates the final answer. It only returns retrieved text; the answer is composed downstream in `query.py`.

---

### `query.py` — Query-Time Retrieval

**What it does:** The main query interface for the RAG system. All queries from the agent and the Q&A UI flow through here.

**Requires:** ChromaDB collections populated by `ingest.py` first (`"tango_tracks"` and `"domain_knowledge"`).

**Three query patterns:**

#### `retrieve_tracks(question, where_filter, n_results)`
Semantic search over `"tango_tracks"`. Accepts an optional ChromaDB `where_filter` dict for hard metadata constraints (e.g., `{"decade": "1930s"}`).

```python
results = retrieve_tracks("romantic tango", where_filter={"decade": "1930s"}, n_results=5)
# → list of dicts with id, document, metadata, distance
```

#### `answer_question(question, include_web_knowledge, llm)`
Full RAG pipeline for natural-language Q&A. Combines:
- Retrieved track context from `"tango_tracks"`
- Retrieved local knowledge chunks from `"domain_knowledge"`
- Optionally fetched background text from `fetch.py` (local markdown → Wikipedia)

Special case: for catalog field questions like "What is the BPM of Así Me Gusta a Mí?", a fast direct-lookup path answers from metadata without a full LLM round-trip.

```python
answer = answer_question("What is the difference between tango and vals?")
# → str, grounded in retrieved context
```

#### `search_for_planning(style, energy_min, energy_max, decade, limit)`
Retrieval helper for the planning agent. Applies hard metadata constraints first (style, decade, energy range), then runs semantic search within those constraints. Returns structured results the agent can use directly for tanda building.

```python
results = search_for_planning(style="tango", decade="1930s", energy_min=0.3, energy_max=0.8)
```

---

### `prompt_to_features.py` — Natural Language → Feature Bundle

**What it does:** Translates a free-text DJ prompt (e.g., "romantic 1940s Di Sarli, smooth and elegant") into a structured feature bundle that `select_tanda.py` and `plan_set.py` can use for scoring and filtering.

**How it works:** A two-layer LLM translation:
1. **Layer 1** — extracts catalog-level fields: style, orchestra, decade, BPM label, energy label, danceability label
2. **Layer 2** — maps the prompt to mood tags and audio characteristics

The bundle is cached per prompt per translator instance — repeated calls with the same prompt skip the LLM entirely.

**Key functions:**
- `load_catalog(path)` — loads and caches the reduced catalog CSV
- `build_translator(catalog_df, provider)` — constructs a translator backed by the specified LLM provider (Claude, Gemini, OpenAI)
- `translator.translate(prompt)` → `TranslationBundle` with a `.merged` dict of all feature fields

---

### `select_tanda.py` — Tanda Selector

**What it does:** Given a feature bundle from `prompt_to_features.py` and a pool of catalog tracks, selects the best single tanda (3–4 tracks) by scoring and ranking.

**Algorithm:**
1. **Hard filter** — strict style match if specified; removes tracks that can't form a valid tanda
2. **Soft filter** — applies looser constraints (decade range, energy range, BPM range) on top of hard filter; falls back to hard-filter pool if no viable groups remain
3. **Scoring** — scores each track against the feature bundle across multiple dimensions (BPM, energy, danceability, decade, orchestra match, tags)
4. **Best tanda** — for each `combo_key` group (tracks sharing orchestra + style + decade), picks the top-scoring tracks that form a valid tanda size; returns the highest mean-scoring group

**Returns:** `TandaResult` with `tanda` (list of track dicts), `combo_key`, `mean_score`, and `query_bundle`.

**Tanda sizes:** Tango = 4 tracks, Vals = 3 tracks, Milonga = 3 tracks (per traditional milonga structure).

---

### `plan_set.py` — Full Milonga Set Planner

**What it does:** Plans a complete milonga set — multiple tandas in a fixed style order — from a single user prompt, with no repeated orchestra/combo across the set.

**Default set schema:** `[tango, tango, vals, tango, tango, milonga]`

**Algorithm:**
1. Translate the user prompt **once** using `prompt_to_features.py` (one LLM call for the whole set)
2. For each slot in the schema, override only the `style` field in the bundle (all mood, energy, and tempo constraints carry through)
3. Run `select_tanda()` on a pool restricted to tracks whose `combo_key` hasn't been used yet
4. Collect results into a `SetResult`

**Usage:**
```bash
python plan_set.py --prompt "romantic 1940s Di Sarli style, smooth and elegant"
python plan_set.py --prompt "..." --schema tango tango vals tango tango milonga
```

```python
from plan_set import plan_set, DEFAULT_SET_SCHEMA
result = plan_set(prompt="energetic D'Arienzo", catalog_df=df)
for slot in result.slots:
    print(slot.combo_key, slot.mean_score)
```

**Returns:** `SetResult` with `slots` (list of `TandaResult`), `set_schema`, `base_bundle`, `used_combo_keys`, and any `warnings` for slots that couldn't be filled.

---

## Evaluation — `tests/test_rag/`

The test suite covers correctness, integration, and performance across the RAG pipeline.

### `test_query_track_retrieval.py`
Validates `retrieve_tracks()` end-to-end against a live ChromaDB instance. Asserts that semantic search with a hard metadata filter (e.g., `{"decade": "1930s"}`) returns only tracks matching that filter. Tests that results are structured correctly (id, metadata, distance).

### `test_search_for_planning.py`
Validates `search_for_planning()` with explicit style and decade constraints. Asserts that every returned track has `style == "tango"` and `decade == "1930s"` — verifying that the structured pre-filter is working before semantic re-ranking.

### `test_answer_question_smoke.py`
A fast smoke test for `answer_question()` using a `FakeLLM` that returns a mock string. Confirms the function returns a non-empty string without requiring a real API call or populated ChromaDB. Safe to run in CI.

### `test_answer_question_real.py`
An integration test using a real LLM call. Submits a domain knowledge question ("What is the difference between tango and vals?") with `include_web_knowledge=True` and asserts the response is a non-empty string. Validates the full retrieval → prompt construction → LLM answer pipeline.

### `test_answer_feature.py`
Tests the catalog field fast-lookup path in `answer_question()`. Submits questions like "What is the BPM of Así Me Gusta a Mí?" and asserts that the word "bpm" (or "year" / a year substring) appears in the response — confirming direct metadata lookup works without a full semantic search + LLM round-trip.

### `test_fetch_simple.py`
Tests `fetch_knowledge()` with a simple named-entity query ("Who is Carlos Di Sarli?"). Validates the returned dict has all required keys (`success`, `source_type`, `source_label`, `source_url`, `content`) and that the internal query normalization produces a clean short lookup string.

### `test_fetch_complex.py`
Tests `fetch_knowledge()` with a complex multi-concept query ("Could you give me some background on the differences between tango and vals for social dancing?"). Asserts that the normalized lookup query is ≤5 words — validating that the keyword extraction step compresses verbose questions into retrieval-friendly form before hitting Wikipedia.

### `test_cache_catalog.py`
Performance test for `load_catalog()` and `_get_catalog_ranges()` module-level caches. Calls each function twice and asserts the second call returns the **same object** (not a copy) and runs orders of magnitude faster — confirming that repeated cold-start costs (CSV parsing, range computation) are paid only once per process.

### `test_cache_llm_translation.py`
Performance test for `BaseTranslator._translation_cache`. Calls `translator.translate()` twice with the same prompt, asserts identity (`b1 is b2`), content equality, and that the cached call is at least 100× faster than the first (LLM) call.

### `test_cache_features_ranges.py`
Minimal regression test for `_get_catalog_ranges()` caching in `select_tanda.py`. Confirms the module-level cache returns the same dict object on repeated calls.

---

## Setup

**Prerequisites:** ChromaDB collections must be built before any query-time module will work.

```bash
# From the project root
python -m atdj.rag.ingest --all --reset
```

**Environment variables** (`.env`):
```
ANTHROPIC_API_KEY=...   # for Claude-backed translation / Q&A
```

**Running tests:**
```bash
# From project root
PYTHONPATH=atdj/rag pytest tests/test_rag/

# Individual scripts that are not pytest-style
PYTHONPATH=atdj/rag python3 tests/test_rag/test_cache_catalog.py
```

---

## Data Files

| File | Description |
|---|---|
| `data/knowledge_base/rag_catalog.csv` | Cleaned track catalog ingested into `"tango_tracks"` |
| `data/reduced_catalog.csv` | Labeled catalog (with `*_label` columns) used by `prompt_to_features` and `select_tanda` |
| `data/knowledge_base/*.md` | Curated domain knowledge (orchestra bios, style notes) ingested into `"domain_knowledge"` |
| `data/chroma_db/` | Persisted ChromaDB on disk (generated by `ingest.py`, not committed) |

---

## Design Decisions

**Why ChromaDB?** It is lightweight, runs locally without a server process, persists to disk, and supports both semantic (embedding) and structured (metadata `where`) filtering in a single query — ideal for a prototype that needs both "find me a romantic tango" and "give me only 1930s tracks".

**Why two collections?** Track documents and knowledge documents have different shapes and retrieval purposes. Keeping them separate avoids cross-collection noise and allows independent reset/rebuild of each.

**Why a singleton ChromaDB client?** Streamlit reruns the Python file on every interaction. A module-level singleton avoids reloading the sentence-transformers embedding model (which takes several seconds) on each rerun.

**Why translate the prompt only once in `plan_set.py`?** All tandas in a milonga set share the same energy and mood arc — only the style changes slot by slot. One LLM call is cheaper and produces more internally consistent sets than calling the translator once per slot.
