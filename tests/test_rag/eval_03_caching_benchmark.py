"""
eval_03_caching_benchmark.py
=============================
Measures speedup from all four caching layers in the AT-DJ pipeline:

  Layer A  — Catalog CSV load            (prompt_to_features._catalog_cache)
  Layer B  — Catalog feature ranges      (select_tanda._catalog_ranges)
  Layer C  — LLM translation             (BaseTranslator._translation_cache)
  Layer D  — Embedding model             (select_tanda SentenceTransformer singleton)

For each layer we measure:
  - cold_s    : first call (no cache)
  - warm_s    : second call (cache hit)
  - speedup_x : cold_s / warm_s
  - saved_ms  : (cold_s - warm_s) * 1000

Additionally we run an end-to-end "full pipeline" comparison:
  - first_call_s  : cold pipeline (all caches empty)
  - repeat_call_s : same prompt, all caches warm
  - e2e_speedup_x

Outputs
-------
- Console table
- eval_03_cache_results.json
- eval_03_cache_summary.csv

Usage
-----
    PYTHONPATH=atdj/rag python3 eval_03_caching_benchmark.py
    PYTHONPATH=atdj/rag python3 eval_03_caching_benchmark.py --csv path/to/catalog.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]   # tests/test_rag/ → project root
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "atdj" / "rag"))

CATALOG_CSV = ROOT / "data" / "reduced_catalog.csv"
TEST_PROMPT = "romantic Di Sarli tango from the 1940s, smooth and lyrical"


# ── Timing helper ─────────────────────────────────────────────────────────

def _time(fn, *args, **kwargs) -> tuple[float, object]:
    """Return (elapsed_seconds, result)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return time.perf_counter() - t0, result


# ── Layer A: Catalog CSV load ─────────────────────────────────────────────

def benchmark_catalog_load(csv_path: str) -> dict:
    from prompt_to_features import load_catalog, _catalog_cache
    _catalog_cache.clear()

    cold_s, df = _time(load_catalog, csv_path)
    warm_s, df2 = _time(load_catalog, csv_path)
    assert df is df2, "Cache miss on second call!"

    return _record("catalog_csv_load", cold_s, warm_s,
                   notes=f"{len(df)} rows loaded")


# ── Layer B: Catalog feature ranges ──────────────────────────────────────

def benchmark_catalog_ranges(df: pd.DataFrame) -> dict:
    import select_tanda as _st
    _st._catalog_ranges = None
    _st._catalog_ranges_key = None

    from select_tanda import _get_catalog_ranges
    cold_s, r1 = _time(_get_catalog_ranges, df)
    warm_s, r2 = _time(_get_catalog_ranges, df)
    assert r1 is r2, "Cache miss on second call!"

    return _record("catalog_feature_ranges", cold_s, warm_s,
                   notes=f"{len(r1)} features cached")


# ── Layer C: LLM translation ──────────────────────────────────────────────

def benchmark_llm_translation(df: pd.DataFrame, prompt: str) -> dict:
    from prompt_to_features import build_translator
    translator = build_translator(df)
    # Clear the cache
    translator._translation_cache.clear()

    cold_s, b1 = _time(translator.translate, prompt)
    warm_s, b2 = _time(translator.translate, prompt)
    assert b1 is b2, "Cache miss on second call!"

    return _record("llm_translation", cold_s, warm_s,
                   notes=f"prompt={prompt[:40]!r}")


# ── Layer D: Embedding model (SentenceTransformer) ────────────────────────

def benchmark_embedding_model() -> dict:
    """
    The embedding model is a module-level singleton in select_tanda.
    We measure the first call to _get_model() vs the second.
    """
    import select_tanda as _st
    # Reset the singleton
    original = _st._model
    _st._model = None

    from select_tanda import _get_model
    cold_s, m1 = _time(_get_model)
    warm_s, m2 = _time(_get_model)
    assert m1 is m2, "Singleton miss on second call!"

    _st._model = original  # restore
    return _record("embedding_model_load", cold_s, warm_s,
                   notes="SentenceTransformer singleton")


# ── End-to-end pipeline ───────────────────────────────────────────────────

def benchmark_e2e_pipeline(df: pd.DataFrame, prompt: str) -> dict:
    """Full pipeline cold vs warm (all caches primed after first run)."""
    from prompt_to_features import build_translator, _catalog_cache
    from select_tanda import select_tanda, _get_catalog_ranges
    import select_tanda as _st

    # Force cold state
    _catalog_cache.clear()
    _st._catalog_ranges = None
    _st._catalog_ranges_key = None
    if _st._model is not None:
        pass  # model already loaded; leave it (realistic scenario)

    translator = build_translator(df)
    translator._translation_cache.clear()

    def _run():
        bundle = translator.translate(prompt)
        result = select_tanda(bundle, df)
        return result

    cold_s, r1 = _time(_run)
    warm_s, r2 = _time(_run)

    rec = _record("e2e_pipeline", cold_s, warm_s,
                  notes="full translate→select round-trip")
    rec["first_call_tanda_size"] = len(r1.get("tanda", []))
    rec["repeat_call_tanda_size"] = len(r2.get("tanda", []))
    return rec


# ── Helper ────────────────────────────────────────────────────────────────

def _record(name: str, cold_s: float, warm_s: float, notes: str = "") -> dict:
    speedup = cold_s / warm_s if warm_s > 0 else float("inf")
    return dict(
        layer=name,
        cold_s=round(cold_s, 4),
        warm_s=round(warm_s, 6),
        speedup_x=round(speedup, 1),
        saved_ms=round((cold_s - warm_s) * 1000, 2),
        notes=notes,
    )


def _print_table(rows: list[dict]) -> None:
    try:
        from rich.table import Table
        from rich.console import Console
        c = Console()
        t = Table(title="Cache Benchmark Results", show_lines=True)
        for col in ["layer", "cold_s", "warm_s", "speedup_x", "saved_ms", "notes"]:
            t.add_column(col)
        for r in rows:
            t.add_row(r["layer"], f"{r['cold_s']:.4f}", f"{r['warm_s']:.6f}",
                      f"{r['speedup_x']:.0f}×", f"{r['saved_ms']:.1f} ms", r["notes"])
        c.print(t)
    except ImportError:
        header = f"{'Layer':<30} {'Cold(s)':>9} {'Warm(s)':>10} {'Speedup':>9} {'Saved(ms)':>10}"
        print("\n" + "=" * len(header))
        print(header)
        print("=" * len(header))
        for r in rows:
            print(f"{r['layer']:<30} {r['cold_s']:>9.4f} {r['warm_s']:>10.6f} "
                  f"{r['speedup_x']:>8.0f}× {r['saved_ms']:>9.1f}")
        print("=" * len(header))


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(CATALOG_CSV))
    parser.add_argument("--prompt", default=TEST_PROMPT)
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--skip-embedding", action="store_true",
                        help="Skip embedding model benchmark (slow cold start)")
    parser.add_argument("--skip-e2e", action="store_true",
                        help="Skip end-to-end pipeline benchmark")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from prompt_to_features import load_catalog
    print(f"Loading catalog from {args.csv} ...")
    df = load_catalog(args.csv)

    results: list[dict] = []

    print("\n── Layer A: Catalog CSV load ──")
    r = benchmark_catalog_load(args.csv)
    results.append(r)
    print(f"  cold={r['cold_s']:.4f}s  warm={r['warm_s']:.6f}s  "
          f"speedup={r['speedup_x']:.0f}×  saved={r['saved_ms']:.1f}ms")

    print("\n── Layer B: Catalog feature ranges ──")
    r = benchmark_catalog_ranges(df)
    results.append(r)
    print(f"  cold={r['cold_s']:.4f}s  warm={r['warm_s']:.6f}s  "
          f"speedup={r['speedup_x']:.0f}×  saved={r['saved_ms']:.1f}ms")

    print("\n── Layer C: LLM translation ──")
    r = benchmark_llm_translation(df, args.prompt)
    results.append(r)
    print(f"  cold={r['cold_s']:.3f}s  warm={r['warm_s']:.6f}s  "
          f"speedup={r['speedup_x']:.0f}×  saved={r['saved_ms']:.0f}ms")

    if not args.skip_embedding:
        print("\n── Layer D: Embedding model singleton ──")
        try:
            r = benchmark_embedding_model()
            results.append(r)
            print(f"  cold={r['cold_s']:.3f}s  warm={r['warm_s']:.6f}s  "
                  f"speedup={r['speedup_x']:.0f}×  saved={r['saved_ms']:.0f}ms")
        except Exception as exc:
            print(f"  [skipped] {exc}")

    if not args.skip_e2e:
        print("\n── End-to-end pipeline ──")
        r = benchmark_e2e_pipeline(df, args.prompt)
        results.append(r)
        print(f"  cold={r['cold_s']:.3f}s  warm={r['warm_s']:.3f}s  "
              f"speedup={r['speedup_x']:.1f}×  saved={r['saved_ms']:.0f}ms")

    print()
    _print_table(results)

    # Totals
    total_saved = sum(r["saved_ms"] for r in results if r["layer"] != "e2e_pipeline")
    print(f"\nTotal latency saved per warm request (layers A+B+C+D): "
          f"{total_saved:.0f} ms ≈ {total_saved/1000:.2f}s")

    # ── Save ──────────────────────────────────────────────────────────────
    json_path = out_dir / "eval_03_cache_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results → {json_path}")

    csv_path = out_dir / "eval_03_cache_summary.csv"
    pd.DataFrame(results).to_csv(csv_path, index=False)
    print(f"✓ Summary → {csv_path}")


if __name__ == "__main__":
    main()
