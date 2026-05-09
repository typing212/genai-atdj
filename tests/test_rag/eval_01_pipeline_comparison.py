"""
eval_01_pipeline_comparison.py
==============================
Head-to-head evaluation: Our two-layer pipeline vs. COT method.

Metrics captured per prompt
---------------------------
- Latency (wall-clock seconds)
- Tanda validity (combo_key coherence, correct size, style constraint)
- Mean composite score of the returned tanda
- Top-5 / bottom-5 individual track scores (sanity window)
- Feature coverage: how many of the 5 composite dimensions the prompt
  actually exercised (our method) vs. how many COT features were selected

Outputs
-------
- Console table (rich if available, plain fallback)
- eval_01_results.json  — full per-prompt records
- eval_01_summary.csv   — flat summary for import into a report

Usage
-----
    # Run from the project root
    PYTHONPATH=atdj/rag python3 eval_01_pipeline_comparison.py

    # Limit to a subset of prompts (fast smoke-test)
    PYTHONPATH=atdj/rag python3 eval_01_pipeline_comparison.py --quick
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── Project path ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]   # tests/test_rag/ → project root
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "atdj" / "rag"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from prompt_to_features import build_translator, load_catalog
from select_tanda import select_tanda

# ── Prompt bank ───────────────────────────────────────────────────────────
# Chosen to stress different dimensions: style, decade, energy, mood, orchestra
ALL_PROMPTS = [
    # Clear/well-specified
    "romantic Di Sarli tango from the 1940s, smooth and lyrical",
    "fast D'Arienzo tango, very danceable, high energy",
    "slow melancholic Pugliese tango, dramatic and intense",
    "lively milonga, fast and playful",
    # Moderately vague
    "something energetic and fast for the dance floor",
    "a calm and relaxed tanda for late in the evening",
    "classic Golden Age tango",
    # Ambiguous / edge-case
    "happy and bright",
    "something dark and brooding from the 1950s",
]

QUICK_PROMPTS = ALL_PROMPTS[:4]

CATALOG_CSV = ROOT / "data" / "reduced_catalog.csv"

# ── Static COT baseline from 02c notebook ────────────────────────────────
# These are the pre-computed aggregate results from
# notebooks/02c_COT_Analysis_ComboAverageBestTanda.ipynb,
# run on the full catalog (294 tracks) with 7 prompts via GPT-4o.
# We use these as the COT reference rather than re-running live,
# because: (a) the 02b/02c notebook env is not packaged as a module,
# (b) those results represent the full feature set run (53 raw Essentia
# features vs our 5 composite dimensions), and (c) it is more honest
# to cite the actual published notebook results.
#
# NOTE on score comparability: COT scores (0.88–1.0) and our composite
# scores (0.69–0.81) are NOT directly comparable — they use entirely
# different scoring functions (raw Essentia feature proximity vs.
# our label-based composite). Only latency, validity rates, and
# feature-count metrics are compared head-to-head.

COT_STATIC = {
    "n_prompts": 7,
    "mean_latency_s": 8.90,
    "min_latency_s": 6.27,
    "max_latency_s": 14.93,
    "std_latency_s": 2.87,
    "has_tanda_rate": 1.00,       # 7/7
    "valid_combo_rate": 1.00,     # 7/7
    "valid_size_rate": 1.00,      # 7/7
    "mean_tanda_score": 0.970,    # COT's own scoring scale — not comparable to ours
    "n_features_selected_mean": 6.4,   # avg features LLM chose from 53 available
    "n_features_available": 53,
    "out_of_bounds_rate": 0.25,   # 25% of predicted ranges exceeded data bounds
    "dataset_coverage_pct": 58.0, # avg % of catalog inside predicted ranges
    "source": "notebooks/02c_COT_Analysis_ComboAverageBestTanda.ipynb",
}


def _print_static_cot_comparison(our_rows: list[dict]) -> None:
    """Print a side-by-side comparison using static COT results from 02c."""
    our_df = pd.DataFrame(our_rows)
    our_latency = pd.to_numeric(our_df["total_latency_s"], errors="coerce")
    our_scores = pd.to_numeric(our_df["mean_tanda_score"], errors="coerce").dropna()

    print("\n" + "=" * 70)
    print("PIPELINE COMPARISON: OUR METHOD vs. COT (02c notebook, n=7)")
    print("=" * 70)
    print(f"{'Metric':<40} {'Our Pipeline':>14} {'COT (02c)':>14}")
    print(f"{'─'*40} {'─'*14} {'─'*14}")

    n_our = len(our_rows)
    print(f"{'n prompts':<40} {n_our:>14} {COT_STATIC['n_prompts']:>14}")

    print(f"\n── Latency ──")
    print(f"{'mean (s)':<40} {our_latency.mean():>14.2f} {COT_STATIC['mean_latency_s']:>14.2f}")
    print(f"{'min (s)':<40} {our_latency.min():>14.2f} {COT_STATIC['min_latency_s']:>14.2f}")
    print(f"{'max (s)':<40} {our_latency.max():>14.2f} {COT_STATIC['max_latency_s']:>14.2f}")
    print(f"{'std (s)':<40} {our_latency.std():>14.2f} {COT_STATIC['std_latency_s']:>14.2f}")

    print(f"\n── Validity (pass rate) ──")
    for flag, cot_key in [("has_tanda", "has_tanda_rate"),
                           ("valid_combo", "valid_combo_rate"),
                           ("valid_size", "valid_size_rate")]:
        our_rate = our_df[flag].apply(bool).mean()
        print(f"  {flag:<38} {our_rate:>13.0%} {COT_STATIC[cot_key]:>13.0%}")

    print(f"\n── Feature usage / interpretability ──")
    our_cov = our_df["feature_coverage"].mean()
    print(f"  {'features used (mean)':<38} {our_cov:>14.1f} {COT_STATIC['n_features_selected_mean']:>14.1f}")
    print(f"  {'features available':<38} {'5 composite':>14} {COT_STATIC['n_features_available']:>14}")
    print(f"  {'out-of-bounds rate':<38} {'N/A (label-based)':>14} {COT_STATIC['out_of_bounds_rate']:>13.0%}")
    print(f"  {'catalog coverage %':<38} {'N/A':>14} {COT_STATIC['dataset_coverage_pct']:>13.0f}%")

    print(f"\n── Score (different scales — not directly comparable) ──")
    if len(our_scores):
        print(f"  {'mean tanda score':<38} {our_scores.mean():>14.4f} {COT_STATIC['mean_tanda_score']:>14.3f}")
    print(f"  {'scoring basis':<38} {'5-dim composite':>14} {'53 raw Essentia':>14}")
    print(f"\n  * COT scores use raw Essentia feature proximity (range ~0.88–1.0).")
    print(f"    Our scores use a weighted label+tag composite (range 0–1).")
    print(f"    These cannot be compared numerically.")
    print(f"\n  Source: {COT_STATIC['source']}")
    print("=" * 70)


# ── Helpers ───────────────────────────────────────────────────────────────

def _tanda_to_scores(tanda_result) -> list[float]:
    """Extract per-track scores from a TandaResult."""
    tracks = tanda_result.tanda or []
    return [float(t.get("composite_score", float("nan"))) for t in tracks]


def _tanda_is_valid(tanda_result, required_style: str | None) -> dict:
    """Return a dict of validity flags."""
    tracks = tanda_result.tanda or []
    if not tracks:
        return dict(has_tanda=False, valid_combo=False,
                    valid_size=False, valid_style=False)
    combo_keys = {t.get("combo_key") for t in tracks}
    styles = {str(t.get("style", "")).lower() for t in tracks}
    tanda_style = tracks[0].get("style") if tracks else None
    required_size = 4 if str(tanda_style).lower() == "tango" else 3
    valid_style = (required_style is None) or (
        required_style.lower() in styles
    )
    return dict(
        has_tanda=True,
        valid_combo=len(combo_keys) == 1,
        valid_size=len(tracks) == required_size,
        valid_style=valid_style,
    )


def _top_bottom_tracks(candidates: list, k: int = 5) -> dict:
    """Return top-k and bottom-k track info from the candidate list."""
    if not candidates:
        return dict(top=[], bottom=[])
    df_c = pd.DataFrame(candidates)
    col = "composite_score" if "composite_score" in df_c.columns else None
    if col is None:
        return dict(top=[], bottom=[])
    df_s = df_c.dropna(subset=[col]).sort_values(col, ascending=False)
    fields = ["title", "orchestra", "singer", "style", "year", col]
    fields = [f for f in fields if f in df_s.columns]
    top = df_s.head(k)[fields].to_dict(orient="records")
    bottom = df_s.tail(k)[fields].to_dict(orient="records")
    return dict(top=top, bottom=bottom)


def _run_our_pipeline(prompt: str, translator, df: pd.DataFrame) -> dict:
    """Run the two-layer pipeline and collect metrics."""
    t0 = time.perf_counter()
    bundle = translator.translate(prompt)
    translation_latency = time.perf_counter() - t0

    t1 = time.perf_counter()
    result = select_tanda(bundle, df)
    selection_latency = time.perf_counter() - t1

    total_latency = translation_latency + selection_latency

    scores = _tanda_to_scores(result)
    style_req = (bundle.merged or {}).get("style")
    validity = _tanda_is_valid(result, style_req)

    COMPOSITE_DIMS = ["bpm_label", "danceability_label", "energy_label",
                      "chords_changes_rate_label", "tags"]
    merged = bundle.merged or {}
    coverage = sum(1 for d in COMPOSITE_DIMS if merged.get(d) not in (None, "", []))

    tb = _top_bottom_tracks(result.candidates)

    return dict(
        method="our_pipeline",
        prompt=prompt,
        translation_latency_s=round(translation_latency, 3),
        selection_latency_s=round(selection_latency, 3),
        total_latency_s=round(total_latency, 3),
        mean_tanda_score=round(float(np.nanmean(scores)), 4) if scores else float("nan"),
        tanda_size=len(scores),
        feature_coverage=coverage,
        **validity,
        top_tracks=tb["top"],
        bottom_tracks=tb["bottom"],
        merged_bundle=merged,
    )


def _print_comparison_table(rows: list[dict]) -> None:
    """Pretty-print side-by-side comparison."""
    try:
        from rich.table import Table
        from rich.console import Console
        console = Console()
        table = Table(title="Pipeline Comparison", show_lines=True)
        for col in ["prompt", "method", "total_latency_s", "mean_tanda_score",
                    "tanda_size", "feature_coverage", "valid_combo",
                    "valid_size", "valid_style"]:
            table.add_column(col, overflow="fold")
        for r in rows:
            table.add_row(*[str(r.get(c, "")) for c in
                            ["prompt", "method", "total_latency_s", "mean_tanda_score",
                             "tanda_size", "feature_coverage", "valid_combo",
                             "valid_size", "valid_style"]])
        console.print(table)
    except ImportError:
        # Plain fallback
        cols = ["method", "total_latency_s", "mean_tanda_score",
                "tanda_size", "feature_coverage", "valid_combo", "valid_size"]
        header = "  ".join(f"{c:>20}" for c in cols)
        print("\n" + "=" * len(header))
        print(header)
        print("=" * len(header))
        for r in rows:
            print("  ".join(f"{str(r.get(c,''))[:20]:>20}" for c in cols))
        print("=" * len(header) + "\n")


def _print_best_worst_tandas(all_our_rows: list[dict]) -> None:
    """Print the best and worst tanda from our pipeline across all prompts."""
    scored = [r for r in all_our_rows if not np.isnan(r.get("mean_tanda_score", float("nan")))]
    if not scored:
        print("[warn] No scored tandas to display.")
        return
    best = max(scored, key=lambda r: r["mean_tanda_score"])
    worst = min(scored, key=lambda r: r["mean_tanda_score"])

    for label, row in [("BEST TANDA", best), ("WORST TANDA", worst)]:
        print(f"\n{'─'*60}")
        print(f"  {label}  |  score={row['mean_tanda_score']:.4f}  |  prompt: {row['prompt']!r}")
        print(f"{'─'*60}")
        print(f"  Top-5 individual tracks (by score):")
        for t in row.get("top_tracks", []):
            s = t.get('score', float('nan'))
            print(f"    {t.get('title', '?'):<40} {t.get('orchestra','?'):<20} score={s:.4f}" if isinstance(s, float) else f"    {t}")
        print(f"  Bottom-5 individual tracks (by score):")
        for t in row.get("bottom_tracks", []):
            s = t.get('score', float('nan'))
            print(f"    {t.get('title', '?'):<40} {t.get('orchestra','?'):<20} score={s:.4f}" if isinstance(s, float) else f"    {t}")


def _aggregate_summary(rows: list[dict]) -> None:
    """Print aggregate statistics by method."""
    df = pd.DataFrame(rows)
    print("\n" + "=" * 60)
    print("AGGREGATE SUMMARY BY METHOD")
    print("=" * 60)
    for method, grp in df.groupby("method"):
        print(f"\n  [{method}]  n={len(grp)}")
        for metric in ["total_latency_s", "mean_tanda_score", "feature_coverage"]:
            vals = pd.to_numeric(grp[metric], errors="coerce").dropna()
            if len(vals):
                print(f"    {metric:<28} mean={vals.mean():.3f}  "
                      f"median={vals.median():.3f}  "
                      f"std={vals.std():.3f}  "
                      f"min={vals.min():.3f}  max={vals.max():.3f}")
        for flag in ["valid_combo", "valid_size", "valid_style", "has_tanda"]:
            if flag in grp.columns:
                rate = grp[flag].apply(lambda x: bool(x)).mean()
                print(f"    {flag:<28} pass_rate={rate:.1%}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Run only the first 4 prompts")
    parser.add_argument("--csv", default=str(CATALOG_CSV))
    parser.add_argument("--out-dir", default=".", help="Where to save outputs")
    parser.add_argument("--model", default=None,
                        help="Override Gemini model name (e.g. gemini-2.0-flash-lite)")
    args = parser.parse_args()

    # Ensure a working model is set — gemini-2.0-flash was deprecated
    import os
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
    elif not os.environ.get("GEMINI_MODEL"):
        os.environ["GEMINI_MODEL"] = "gemini-2.0-flash-lite"

    prompts = QUICK_PROMPTS if args.quick else ALL_PROMPTS
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading catalog from {args.csv} ...")
    df = load_catalog(args.csv)
    print(f"  {len(df)} tracks loaded.")

    print("Building translator ...")
    translator = build_translator(df)

    all_rows: list[dict] = []

    for i, prompt in enumerate(prompts, 1):
        print(f"\n[{i}/{len(prompts)}] {prompt!r}")
        our_row = _run_our_pipeline(prompt, translator, df)
        print(f"  our_pipeline  latency={our_row['total_latency_s']:.2f}s  "
              f"score={our_row['mean_tanda_score']}")
        all_rows.append(our_row)

    # ── Display ───────────────────────────────────────────────────────────
    _print_comparison_table(all_rows)
    _print_best_worst_tandas(all_rows)
    _aggregate_summary(all_rows)
    _print_static_cot_comparison(all_rows)

    # ── Save ──────────────────────────────────────────────────────────────
    json_path = out_dir / "eval_01_results.json"
    # Strip un-serialisable objects before saving
    saveable = []
    for r in all_rows:
        sr = {k: v for k, v in r.items()
              if k not in ("merged_bundle",)}
        saveable.append(sr)
    with open(json_path, "w") as f:
        json.dump(saveable, f, indent=2, default=str)
    print(f"\n✓ Full results  → {json_path}")

    # Flat CSV (drop nested lists)
    flat_rows = []
    for r in saveable:
        flat_rows.append({k: v for k, v in r.items()
                          if not isinstance(v, (list, dict))})
    csv_path = out_dir / "eval_01_summary.csv"
    pd.DataFrame(flat_rows).to_csv(csv_path, index=False)
    print(f"✓ Flat summary  → {csv_path}")


if __name__ == "__main__":
    main()
