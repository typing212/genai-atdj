# Branch Merge Plan
**vanessaz (yours) + nancy-upload + tina → final merged vanessaz**

---

## STATUS LEGEND
- ✅ Done — staged and ready to commit
- ⚠️ Needs fix — file is in place but has an issue
- ❌ Not yet done
- ⏭️ Skip — intentionally excluded

---

## 1. File Ownership Map

### Files Nancy added (not in vanessaz at all)

```
✅ atdj/rag/fetch.py                          RAG knowledge fetcher (local md + Wikipedia)
✅ atdj/rag/ingest.py                         ChromaDB catalog + knowledge ingest
✅ atdj/rag/query.py                          RAG Q&A pipeline
✅ atdj/rag/select_tanda.py                   Filter + score + pick best tanda
✅ atdj/rag/store.py                          ChromaDB client setup
✅ atdj/rag/prompt_to_features.py             NL prompt → structured feature bundle
✅ atdj/rag/debug_select_tanda.py             Debug script for select_tanda
✅ atdj/rag/example_steps.md                  Expected debug output
✅ data/knowledge_base/rag_catalog.csv        295-track catalog for RAG
✅ data/knowledge_base/tango_vs_vals_milonga.md  Domain knowledge file
✅ data/reduced_catalog.csv                   Same 295-track catalog (duplicate)
✅ notebooks/02a_data_feature_prep_v3.ipynb   Latest data prep notebook
✅ notebooks/generate_rag_catalog.ipynb       How rag_catalog.csv was built
✅ tests/test_rag/  (7 files)                 RAG test suite
```

### Files Tina added (not in vanessaz at all)

```
✅ atdj/features/extractors/essentia_extract.py   Already in vanessaz (yours, not Tina's)
✅ atdj/features/extractors/librosa_extract.py    Already in vanessaz (yours, not Tina's)
✅ atdj/features/eda_notebooks/librosa_eda.ipynb  Already in vanessaz (yours, not Tina's)
✅ data/processed/essentia_*.csv (3 files)        Already in vanessaz (yours, not Tina's)
✅ data/processed/librosa_*.csv (2 files)         Already in vanessaz (yours, not Tina's)
✅ notebooks/06_agent_prototype.ipynb             Staged — Tina's latest version checked out
⏭️ doc/session_log_*.json (30+ files)             Test run outputs — SKIP
```

### Files BOTH Nancy and Tina changed (vs vanessaz)

These are the files that will have merge conflicts:

```
✅ atdj/config.py           Fixed — CHROMA_DIR=chroma_db, KNOWLEDGE_DIR=knowledge_base, RAG_CATALOG_PATH added
✅ atdj/agent/state.py      Tina's version — has agent_log + activity_log
✅ atdj/agent/nodes.py      Tina's version — real LLM calls, search_catalog_rag
✅ atdj/agent/tools.py      Tina's version — has search_catalog_rag
✅ atdj/ui/app.py           Your version kept
✅ atdj/ui/page_main.py     Your base + Tina's agent chat block + Tina's _section_log()
```

---

## 2. Tina Copied from Nancy — What's the Same, What Diverged

Tina manually copied Nancy's RAG files in commit `ba00a90` ("add RAG files
and reduced catalog from nancy-upload"). Then Nancy pushed one more commit
(`0e8a363`) AFTER Tina copied.

**Result:**

| File group | Tina vs Nancy — same or different? |
|---|---|
| `atdj/rag/*.py` (all 6 RAG files) | **IDENTICAL** — Tina's copy matches Nancy's latest |
| `data/reduced_catalog.csv` | **IDENTICAL** |
| `atdj/config.py` | **CORRECTION from earlier plan** — Tina's config is SAME as vanessaz (no RAG paths). Nancy's has different paths. See Section 3. |
| `atdj/agent/nodes.py` | **DIFFERENT** — Tina has full implementation; Nancy has simpler stubs |
| `atdj/agent/tools.py` | **DIFFERENT** — Tina has `search_catalog_rag`; Nancy does not |
| `atdj/agent/state.py` | **DIFFERENT** — Tina added `agent_log` and `activity_log` |
| `atdj/ui/page_main.py` | **DIFFERENT** — Tina has real agent routing; Nancy has chat stubs |
| `data/knowledge_base/` | **ONLY IN NANCY** — Tina never got these files |
| `tests/test_rag/` | **ONLY IN NANCY** — Tina never got these |

---

## 3. Conflict Details — What to Keep from Each Branch

### `atdj/config.py` ✅ FIXED

```
Your vanessaz (= Tina's version — they are identical):
  CATALOG_PATH  = data/essentia_newsamp.csv      ← used by playback + agent tools
  CHROMA_DIR    = data/chroma_store              ← OLD path, RAG uses chroma_db
  KNOWLEDGE_DIR = data/domain_knowledge          ← OLD path, RAG files are in knowledge_base

Nancy's version:
  CATALOG_PATH  = data/knowledge_base/rag_catalog.csv
  CHROMA_DIR    = data/chroma_db                 ← What store.py expects
  KNOWLEDGE_DIR = data/knowledge_base            ← What fetch.py and ingest.py expect
  OPENAI_API_KEY / OPENAI_MODEL = "gpt-5-mini"  ← typo, should be gpt-4o-mini
```

**Problem:** Nancy's RAG files (store.py, fetch.py, ingest.py) import CHROMA_DIR,
KNOWLEDGE_DIR, CATALOG_PATH from config. Current config has wrong paths for these.

**Fix needed in atdj/config.py:**
```python
# Change:
CHROMA_DIR    = DATA_DIR / "chroma_store"
KNOWLEDGE_DIR = DATA_DIR / "domain_knowledge"
CATALOG_PATH  = DATA_DIR / "essentia_newsamp.csv"

# To (keep CATALOG_PATH for playback/agent, add separate RAG path):
CHROMA_DIR       = DATA_DIR / "chroma_db"            # RAG ChromaDB location
KNOWLEDGE_DIR    = DATA_DIR / "knowledge_base"        # RAG .md files location
CATALOG_PATH     = DATA_DIR / "essentia_newsamp.csv"  # keep for playback/agent
RAG_CATALOG_PATH = DATA_DIR / "knowledge_base" / "rag_catalog.csv"  # RAG catalog
```

Then update atdj/rag/ingest.py line that imports CATALOG_PATH to use RAG_CATALOG_PATH instead.

---

### `atdj/agent/state.py` ✅ DONE

Tina's version staged. Has all Nancy's fields PLUS:
- `agent_log: list[str]`
- `activity_log: Annotated[list[LogEntry], operator.add]`

---

### `atdj/agent/tools.py` ✅ DONE

Tina's version staged. Has `search_catalog_rag` on top of Nancy's tools.

---

### `atdj/agent/nodes.py` ✅ DONE

Tina's version staged. Real LLM calls, search_catalog_rag, activity_log, session JSON.

---

### `atdj/ui/page_main.py` ✅ DONE

Your vanessaz base + Tina's PLAN/QUESTION chat routing block + Tina's _section_log().

---

## 4. Step-by-Step Merge Commands

### Step 1 — Merge Nancy first ✅ IN PROGRESS (MERGE_HEAD active, all conflicts resolved)

```bash
# Already done. All Nancy files staged. Key conflict resolutions:
# - agent/state.py, nodes.py, tools.py → took Tina's versions during resolution
# - ui/page_main.py → manually merged (your base + Tina's chat block)
# - pyproject.toml, uv.lock → took Tina's versions
```

### Step 2 — Add remaining Tina-only files ✅ DONE

Since the Nancy merge already has Tina's key files (via git checkout during resolution),
we just need to checkout Tina's remaining unique files and stage them before committing:

```bash
# Tina's feature extractors (not in Nancy or vanessaz)
git checkout origin/tina -- atdj/features/extractors/essentia_extract.py
git checkout origin/tina -- atdj/features/extractors/librosa_extract.py
git checkout origin/tina -- atdj/features/eda_notebooks/librosa_eda.ipynb
git add atdj/features/

# Tina's processed feature CSVs
git checkout origin/tina -- data/processed/essentia_milonga.csv
git checkout origin/tina -- data/processed/essentia_tango.csv
git checkout origin/tina -- data/processed/essentia_vals.csv
git checkout origin/tina -- data/processed/librosa_milonga.csv
git checkout origin/tina -- data/processed/librosa_vals.csv
git add data/processed/

# Tina's notebook
git checkout origin/tina -- notebooks/06_agent_prototype.ipynb
git add notebooks/06_agent_prototype.ipynb

# Empty __init__.py files Tina added
git checkout origin/tina -- atdj/audio/__init__.py
git checkout origin/tina -- atdj/playback/__init__.py
git add atdj/audio/__init__.py atdj/playback/__init__.py
```

### Step 2b — Fix config.py ✅ DONE

```python
# In atdj/config.py, change:
CHROMA_DIR    = DATA_DIR / "chroma_store"
KNOWLEDGE_DIR = DATA_DIR / "domain_knowledge"

# To:
CHROMA_DIR       = DATA_DIR / "chroma_db"
KNOWLEDGE_DIR    = DATA_DIR / "knowledge_base"

# And add after CATALOG_PATH line:
RAG_CATALOG_PATH = DATA_DIR / "knowledge_base" / "rag_catalog.csv"
```

```bash
# Then update ingest.py to use RAG_CATALOG_PATH:
# In atdj/rag/ingest.py, change:
#   from atdj.config import CATALOG_PATH, KNOWLEDGE_DIR
# To:
#   from atdj.config import RAG_CATALOG_PATH as CATALOG_PATH, KNOWLEDGE_DIR
git add atdj/config.py atdj/rag/ingest.py
```

### Step 3 — One single commit for everything ❌ NOT YET DONE

```bash
git commit -m "Merge nancy-upload + tina: RAG pipeline, agent core, enhancement hook, activity log"
```

### Step 4 — Verify the merge ❌ NOT YET DONE

```bash
# 1. Check imports work
uv run python -c "
from atdj.agent.graph import build_graph
from atdj.audio.enhancement import enhance_tanda
from atdj.rag.query import answer_question
from atdj.rag.select_tanda import select_tanda
print('All imports OK')
"

# 2. Check enhancement pipeline directly
uv run python -c "
from pathlib import Path
from atdj.audio.enhancement import enhance_tanda
tracks = list(Path('data/raw').glob('*.mp3'))[:2]
if tracks:
    results = enhance_tanda(tracks, Path('data/processed'))
    for r in results: print(r['name'], 'SNR delta:', round(r['snr_delta'], 1), 'dB')
else:
    print('No audio files in data/raw — enhancement not testable yet')
"

# 3. Run the RAG tests
uv run pytest tests/test_rag/ -v

# 4. Start the app
uv run streamlit run main.py
```

---

## 5. Quick Reference — Who Wins Each File

| File | Status | Winner | Notes |
|---|---|---|---|
| `atdj/rag/*.py` (all 6) | ✅ | Nancy = Tina (same) | Staged |
| `atdj/config.py` | ✅ | Yours + fixes | CHROMA_DIR=chroma_db, KNOWLEDGE_DIR=knowledge_base, RAG_CATALOG_PATH added |
| `atdj/agent/state.py` | ✅ | Tina | Staged |
| `atdj/agent/nodes.py` | ✅ | Tina | Staged |
| `atdj/agent/tools.py` | ✅ | Tina | Staged |
| `atdj/ui/app.py` | ✅ | Yours | Staged |
| `atdj/ui/page_main.py` | ✅ | Yours + Tina chat | Staged |
| `atdj/audio/enhancement.py` | ✅ | Yours | Already in vanessaz |
| `atdj/playback/player.py` | ✅ | Yours | Already in vanessaz |
| `atdj/ui/audio_player.py` | ✅ | Yours | Already in vanessaz |
| `atdj/audio/__init__.py` | ✅ | Tina | Staged |
| `atdj/playback/__init__.py` | ✅ | Tina | Staged |
| `atdj/features/extractors/*.py` | ✅ | Yours | Already in vanessaz |
| `data/processed/essentia_*.csv` | ✅ | Yours | Already in vanessaz |
| `data/processed/librosa_*.csv` | ✅ | Yours | Already in vanessaz |
| `notebooks/06_agent_prototype.ipynb` | ✅ | Tina | Staged (Tina's latest) |
| `data/knowledge_base/` | ✅ | Nancy | Staged |
| `tests/test_rag/` | ✅ | Nancy | Staged |
| `doc/session_log_*.json` | ⏭️ | Skip | Test noise, do not commit |
