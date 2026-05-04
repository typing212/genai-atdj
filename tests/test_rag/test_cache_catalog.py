"""
test_cache_catalog.py
---------------------
Tests for load_catalog caching and _get_catalog_ranges caching.

Run from the project root (genai-atdj/) with:
    PYTHONPATH=atdj/rag python3 tests/test_rag/test_cache_catalog.py

Or from atdj/rag/ with:
    PYTHONPATH=. python3 ../../tests/test_rag/test_cache_catalog.py
"""

import sys
import time
from pathlib import Path

# ── Resolve the catalog path robustly ─────────────────────────────────────
# Works regardless of which directory you run from.
THIS_FILE   = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]          # genai-atdj/
CATALOG_CSV  = PROJECT_ROOT / "data" / "reduced_catalog.csv"

# Fallback: if the repo keeps the CSV in atdj/rag/ directly
if not CATALOG_CSV.exists():
    CATALOG_CSV = THIS_FILE.parent / "reduced_catalog.csv"

if not CATALOG_CSV.exists():
    print(f"ERROR: Cannot find reduced_catalog.csv. Tried:\n"
          f"  {PROJECT_ROOT / 'data' / 'reduced_catalog.csv'}\n"
          f"  {THIS_FILE.parent / 'reduced_catalog.csv'}")
    sys.exit(1)

print(f"Using catalog: {CATALOG_CSV}\n")

# ── Test 1: load_catalog caching ──────────────────────────────────────────
from prompt_to_features import load_catalog, _catalog_cache

print("=" * 50)
print("TEST 1 — load_catalog module-level cache")
print("=" * 50)

_catalog_cache.clear()   # ensure cold start

t0 = time.perf_counter()
df1 = load_catalog(CATALOG_CSV)
t1 = time.perf_counter() - t0
print(f"First call  (cold): {t1:.4f}s  — {len(df1)} rows loaded")

t0 = time.perf_counter()
df2 = load_catalog(CATALOG_CSV)
t2 = time.perf_counter() - t0
print(f"Second call (cache): {t2:.6f}s")

assert df1 is df2, "Cache miss: got a different DataFrame object on second call"
print("✓ same object returned — cache is working\n")

# ── Test 2: _get_catalog_ranges caching ───────────────────────────────────
from select_tanda import _get_catalog_ranges, _catalog_ranges

print("=" * 50)
print("TEST 2 — _get_catalog_ranges module-level cache")
print("=" * 50)

import select_tanda as _st_mod
_st_mod._catalog_ranges = None       # reset cache
_st_mod._catalog_ranges_key = None

t0 = time.perf_counter()
r1 = _get_catalog_ranges(df1)
t1 = time.perf_counter() - t0
print(f"First call  (cold): {t1:.6f}s")
print(f"  Ranges: { {k: tuple(round(v,3) for v in vs) for k, vs in r1.items()} }")

t0 = time.perf_counter()
r2 = _get_catalog_ranges(df1)
t2 = time.perf_counter() - t0
print(f"Second call (cache): {t2:.6f}s")

assert r1 is r2, "Cache miss: got a different dict object on second call"
print("✓ same dict object returned — cache is working\n")

print("All tests passed ✓")
