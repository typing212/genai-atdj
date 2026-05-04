"""
test_cache_llm_translation.py
------------------------------
Tests that BaseTranslator._translation_cache avoids a second LLM call
when the same prompt is submitted twice within the same translator instance.

Run from any directory:
    PYTHONPATH=atdj/rag python3 tests/test_rag/test_cache_llm_translation.py

Or from atdj/rag/:
    PYTHONPATH=. python3 ../../tests/test_rag/test_cache_llm_translation.py
"""

import sys
import time
from pathlib import Path

# ── Resolve catalog path robustly ─────────────────────────────────────────
THIS_FILE    = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
CATALOG_CSV  = PROJECT_ROOT / "data" / "reduced_catalog.csv"

if not CATALOG_CSV.exists():
    CATALOG_CSV = THIS_FILE.parent / "reduced_catalog.csv"

if not CATALOG_CSV.exists():
    print(f"ERROR: Cannot find reduced_catalog.csv. Tried:\n"
          f"  {PROJECT_ROOT / 'data' / 'reduced_catalog.csv'}\n"
          f"  {THIS_FILE.parent / 'reduced_catalog.csv'}")
    sys.exit(1)

print(f"Using catalog: {CATALOG_CSV}\n")

# ── Run test ──────────────────────────────────────────────────────────────
from prompt_to_features import load_catalog, build_translator

df = load_catalog(CATALOG_CSV)
t  = build_translator(df)   # uses LLM_PROVIDER env var

prompt = "energetic D'Arienzo tango, fast and danceable"

print("=" * 50)
print("TEST — LLM translation cache")
print("=" * 50)

t0 = time.perf_counter()
b1 = t.translate(prompt)
elapsed_llm = time.perf_counter() - t0
print(f"First call  (LLM):   {elapsed_llm:.3f}s")
print(f"  merged: {b1.merged}")

t0 = time.perf_counter()
b2 = t.translate(prompt)
elapsed_cache = time.perf_counter() - t0
print(f"Second call (cache): {elapsed_cache:.6f}s")
print(f"  merged: {b2.merged}")

# Identity check — cache must return the exact same object
assert b1 is b2, "Cache miss: got a different TranslationBundle object on second call"

# Content check — merged dicts must be identical (catches copy-before-cache bugs)
assert b1.merged == b2.merged, f"Merged dicts differ:\n  {b1.merged}\n  {b2.merged}"

# Speed check — cached call should be at least 100x faster than the LLM call
assert elapsed_cache < elapsed_llm / 100, (
    f"Cache doesn't seem to be working — "
    f"second call took {elapsed_cache:.4f}s vs first call {elapsed_llm:.3f}s"
)

print(f"\n✓ translation cache is working  "
      f"(speedup: {elapsed_llm / max(elapsed_cache, 1e-9):.0f}x)\n")
