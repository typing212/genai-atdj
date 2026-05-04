"""
Run from rag folder:
PYTHONPATH=. python3 ../../tests/test_rag/test_cache_features_ranges.py
"""

import pandas as pd
from select_tanda import _get_catalog_ranges

df = pd.read_csv("../../data/reduced_catalog.csv")

import time

t0 = time.perf_counter()
r1 = _get_catalog_ranges(df)
print(f"First call:  {time.perf_counter()-t0:.6f}s")

t0 = time.perf_counter()
r2 = _get_catalog_ranges(df)
print(f"Second call: {time.perf_counter()-t0:.6f}s")  # should be ~0.000001s

assert r1 is r2  # same dict object returned
print("✓ cache is working")