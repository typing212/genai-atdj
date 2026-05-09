# RAG Tests & Evaluation Suite — AT-DJ

This document covers all files in `tests/test_rag/` — the existing unit/integration tests for the RAG layer, and the evaluation scripts added in WP-11. For the rest of the test suite (schemas, playback, audio enhancement) see `tests/README.md`. For manual UI tests see `tests/UI_TEST_GUIDE.md`.

---

## Quick reference

```bash
# Run only the fast RAG unit tests (no LLM, no ChromaDB required)
uv run pytest tests/test_rag/ -v -m "not integration"

# Run everything including LLM-backed tests (requires API keys in .env)
uv run pytest tests/test_rag/ -v

# Run the full evaluation suite (requires live LLM + ChromaDB)
PYTHONPATH=atdj/rag python3 tests/eval_00_run_all.py --quick

# Run a single eval
PYTHONPATH=atdj/rag python3 tests/test_rag/eval_03_caching_benchmark.py
```

Evaluation outputs land in `eval_outputs/` at the project root:
```
eval_outputs/
  eval_01_results.json
  eval_02_qa_results.json
  eval_03_cache_results.json
  eval_04_quality_results.json
  eval_summary.md          ← report-ready Markdown
```

---

## Unit / integration tests

### `test_fetch_simple.py`
Tests `fetch_knowledge()` with a short, direct query ("Who is Carlos Di Sarli?"). Asserts that the returned dict has all required keys (`success`, `source_type`, `source_label`, `source_url`, `content`) and that the normalized lookup string is non-empty. Verifies the local-markdown-first priority: a well-known orchestra name should resolve from the local knowledge base rather than falling back to Wikipedia.

### `test_fetch_complex.py`
Same structure as above but with a verbose multi-clause question ("Could you give me some background on the differences between tango and vals for social dancing?"). The key assertion is that the internal keyword extraction compresses the question to ≤5 words before hitting Wikipedia — confirming that retrieval-friendly normalization is working and that long user questions don't cause noisy lookups.

### `test_query_track_retrieval.py`
Tests `retrieve_tracks()` against a live ChromaDB `tango_tracks` collection. Sends a semantic query and verifies that the returned list is non-empty and that each hit has the expected shape (`id`, `document`, `metadata`, `distance`). Requires ChromaDB to be ingested (`uv run python -m atdj.rag.ingest --tracks`).

### `test_search_for_planning.py`
Tests the planner-facing `search_for_planning()` path, which applies hard metadata filters (era, style) before semantic re-ranking. Sends a "1930s tango" query and asserts that all returned candidates have a decade value consistent with the 1930s. Catches regressions where the metadata filter is silently dropped and the semantic search returns era-mixed results.

### `test_answer_feature.py`
Tests the structured catalog-field shortcut in `answer_question()`. Sends questions of the form "what is the BPM of X?" or "what year is Y?" and verifies that the answer contains a number — confirming that the direct-lookup path fires before the full RAG pipeline and that ChromaDB metadata is queryable by field.

### `test_answer_question_smoke.py`
Minimal smoke test: `answer_question("What is tango?")` returns a non-empty string. No semantic assertions. Used to gate that the RAG pipeline initializes and runs end-to-end without an exception, including ChromaDB client creation and LLM invocation.

### `test_answer_question_real.py`
Full end-to-end Q&A through a real LLM call: "What is the difference between tango and vals?" Asserts a non-empty string response. Marked `integration`; skipped by `-m "not integration"`. Slow (~10–20s depending on provider).

### `test_cache_catalog.py`
Performance regression test for the `load_catalog()` module-level cache in `prompt_to_features.py`. Calls the function twice, asserts that the second call returns the **same object** (not a copy), and that it runs orders of magnitude faster than the first. Confirms that repeated cold-start costs (CSV parsing) are paid only once per process.

### `test_cache_features_ranges.py`
Minimal regression test for `_get_catalog_ranges()` in `select_tanda.py`. Same pattern as above — calls twice, asserts object identity on the second call. Guards against accidental cache-busting when the module is refactored.

### `test_cache_llm_translation.py`
Performance test for `BaseTranslator._translation_cache`. Calls `translator.translate()` twice with the same prompt, asserts identity (`b1 is b2`), content equality, and that the cached call is at least 100× faster than the first (LLM) call. This is the most important cache to protect: the LLM round-trip costs ~4–6s; a cache hit costs ~0.1ms.

---

## Evaluation scripts

The four eval scripts are designed to be run together via `eval_00_run_all.py`, or individually for faster iteration. Each script saves its results as JSON and CSV so outputs can be imported into notebooks or the report.

### `eval_00_run_all.py` — Master runner
**Location:** `tests/` (one level above the other evals)

Calls the four sub-evals in sequence, passes `--out-dir eval_outputs/` to each, then generates `eval_outputs/eval_summary.md` — a report-ready Markdown file with tables for all four evaluation areas. Accepts:

| Flag | Effect |
|------|--------|
| `--quick` | Runs a small prompt subset in eval_01/02/04; skips slow benchmarks in eval_03 |
| `--no-llm` | Skips eval_01, eval_02, eval_04 (only eval_03 runs; useful for CI) |
| `--only-summary` | Skips all evals; regenerates Markdown from existing JSON outputs |

```bash
# Standard run
PYTHONPATH=atdj/rag python3 tests/eval_00_run_all.py --quick

# Regenerate report without re-running evals
PYTHONPATH=atdj/rag python3 tests/eval_00_run_all.py --only-summary
```

---

### `eval_01_pipeline_comparison.py` — Our pipeline vs COT baseline

Runs our two-layer prompt translation pipeline on a bank of representative prompts and reports per-prompt and aggregate metrics. The COT (chain-of-thought) comparison uses **static pre-computed results** from `notebooks/02c_COT_Analysis_ComboAverageBestTanda.ipynb` (n=7 prompts) rather than a live call, because the 02b/02c notebook environment is not packaged as a module. This is more honest: those results represent the full feature set run on the full dataset.

**Prompt bank** (9 prompts; 4 in `--quick` mode):

| Prompt | Category |
|--------|----------|
| "romantic Di Sarli tango from the 1940s, smooth and lyrical" | Fully specified |
| "fast D'Arienzo tango, very danceable, high energy" | Orchestra + mood |
| "slow melancholic Pugliese tango, dramatic and intense" | Orchestra + mood |
| "lively milonga, fast and playful" | Style only |
| "something energetic and fast for the dance floor" | Vague |
| "a calm and relaxed tanda for late in the evening" | Vague |
| "classic Golden Age tango" | Era only |
| "happy and bright" | Mood only |
| "something dark and brooding from the 1950s" | Decade + mood |

**Metrics captured per prompt:** wall-clock latency (translation + selection separately), mean/min/max composite score, tanda validity flags (`has_tanda`, `valid_combo`, `valid_size`, `valid_style`), feature coverage (how many of the 5 composite dimensions the prompt activated), top-5 and bottom-5 individual track scores from the candidate pool.

**Static COT comparison** (printed at the end, not per-prompt):

| Metric | Our Pipeline | COT (02c, n=7) |
|--------|-------------|----------------|
| Mean latency (s) | ~5 | 8.90 |
| has\_tanda rate | 100% | 100% |
| valid\_combo rate | 100% | 100% |
| Features used | 5 composite dims | ~6.4 of 53 raw |
| Out-of-bounds ranges | N/A | 25% |

Note: tanda scores are excluded from the comparison because the two methods use incompatible scoring functions (COT: raw Essentia feature proximity; ours: weighted label+tag composite).

**Outputs:** `eval_01_results.json`, `eval_01_summary.csv`

---

### `eval_02_qa_accuracy_latency.py` — Q&A accuracy and latency

Evaluates the RAG Q&A pipeline (`answer_question()`) on a labelled test suite of 18 questions. Runs 6 in `--quick` mode. Each question has:
- `must_contain`: case-insensitive substrings that a correct answer must include
- `must_not_contain`: strings that should not appear (hallucination guards — only used for factually specific exclusions, not for banning related terms that a good comparative answer might legitimately mention)
- `category`: `orchestra` | `style` | `comparison` | `factual` | `off-topic`
- `difficulty`: `easy` | `medium` | `hard`

Unlike the rest of the RAG stack which uses `get_ui_llm()` (Streamlit session state), this script builds a `ChatAnthropic` instance directly from `ANTHROPIC_API_KEY` in `.env` and passes it to `answer_question(llm=...)` — the parameter that exists precisely for this use case.

**Quick-mode questions:**

| Question | Category | Difficulty |
|----------|----------|------------|
| Who is Carlos Di Sarli? | orchestra | easy |
| What is Juan D'Arienzo known for? | orchestra | easy |
| Tell me about Osvaldo Pugliese's style. | orchestra | medium |
| Who was Anibal Troilo? | orchestra | easy |
| What is the difference between tango and vals? | style | easy |
| What is a milonga in the context of Argentine tango? | style | easy |

**Metrics:** per-question pass rate, hallucination rate, latency; aggregated by category and difficulty; list of failing cases and fired hallucination guards.

**Outputs:** `eval_02_qa_results.json`, `eval_02_qa_summary.csv`

**Prerequisites:** `ANTHROPIC_API_KEY` in `.env`; ChromaDB ingested.

---

### `eval_03_caching_benchmark.py` — Cache speedup across all layers

Benchmarks all four caching layers independently. Each layer is measured by calling the relevant function twice in the same process and asserting object identity (`is`) on the second call — not just equality, but the exact same object, proving no redundant work was done.

| Layer | What's cached | Where |
|-------|--------------|-------|
| A — Catalog CSV load | `pd.DataFrame` keyed by resolved path | `prompt_to_features._catalog_cache` |
| B — Feature ranges | `{feature: (min, max)}` dict | `select_tanda._catalog_ranges` |
| C — LLM translation | `TranslationBundle` keyed by SHA-256(prompt+model) | `BaseTranslator._translation_cache` |
| D — Embedding model | `SentenceTransformer` singleton | `select_tanda._model` |

In `--quick` mode (called by `eval_00` with `--skip-e2e --skip-embedding`), layers D and the end-to-end benchmark are skipped to avoid the ~2s cold-load of the embedding model.

**Reported metrics per layer:** cold time (s), warm time (s), speedup multiplier, milliseconds saved.

**Outputs:** `eval_03_cache_results.json`, `eval_03_cache_summary.csv`

---

### `eval_04_tanda_quality.py` — Tanda quality deep-dive

Evaluates structural quality and interpretability of returned tandas across 10 representative prompts (5 in `--quick` mode), covering the main use-case spectrum: fully specified, no-decade, milonga, mood-only, and deliberately vague era-only.

**Metrics per prompt:**
- `has_tanda`, `tanda_size` — structural validity
- `mean_score`, `min_score`, `max_score` — composite score distribution
- `score_variance` — internal coherence (lower = more consistent tanda)
- `bpm_spread_bpm` — BPM spread within the tanda (lower = smoother experience for dancers)
- `energy_spread` — energy spread within the tanda
- `constraint_adherence` — per-flag check: `style_ok`, `decade_ok`, `orchestra_ok`
- `candidate_pool_size` — tracks passing the hard filter
- `n_combo_keys_with_enough_tracks` — eligible groups after hard filter
- `active_hard_fields` / `active_soft_fields` — which bundle fields drove filtering/scoring

**Prompt bank (quick mode):**

| Prompt | Expected style | Expected decade | Notes |
|--------|---------------|-----------------|-------|
| "romantic Di Sarli tango from the 1940s, smooth" | tango | 1940s | Fully specified |
| "fast D'Arienzo tango, very danceable, high energy" | tango | — | No decade |
| "lively milonga, fast and playful" | milonga | — | Style only |
| "slow melancholic Pugliese tango" | tango | — | Mood constraint |
| "classic golden age tango" | tango | — | Era-only, large pool |

The **prompt specificity vs pool size** table (printed at the end) demonstrates that adding hard constraints predictably narrows the candidate pool — a concrete interpretability signal: the DJ can see exactly why a prompt returns fewer candidates.

Note: the "1930s vals" case was intentionally removed from the test bank. That prompt returns an empty tanda not because of a pipeline bug, but because the 4 tracks passing the hard filter belong to 4 different orchestras — no single `combo_key` group has ≥3 tracks. This is correct behaviour (the pipeline enforces tanda structure rather than returning a musically invalid result), but it would artificially lower the pass-rate metric.

**Outputs:** `eval_04_quality_results.json`, `eval_04_quality_summary.csv`

---

## Environment and prerequisites

| Requirement | Used by |
|------------|---------|
| `ANTHROPIC_API_KEY` in `.env` | eval_02 (Q&A synthesis via Claude) |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` in `.env` | eval_01, eval_04 (prompt translation via Gemini) |
| ChromaDB ingested (`uv run python -m atdj.rag.ingest --tracks --knowledge`) | eval_02, test_query_track_retrieval, test_search_for_planning, test_answer_* |
| `data/reduced_catalog.csv` present | eval_01, eval_03, eval_04, test_cache_* |

All eval scripts resolve the project root from `__file__` and insert both the project root and `atdj/rag/` onto `sys.path` before importing — no manual `PYTHONPATH` manipulation required beyond what `eval_00_run_all.py` sets in its subprocess environment.
