"""
eval_04_tanda_quality.py
=========================
Deep-dive quality evaluation of the tanda selection pipeline.

Dimensions evaluated
--------------------
1. Constraint adherence
   - Hard: style, decade, orchestra, singer — must be 100% honoured
   - Soft: bpm_label, energy, danceability — scored for proximity

2. Tanda internal coherence
   - Score variance (lower = more internally consistent tanda)
   - BPM spread within tanda (lower = smoother experience)
   - Energy spread within tanda

3. Feature attribution / interpretability
   - Which bundle fields actually caused the hard filter to shrink the pool?
   - How selective was the soft filter?
   - How much does tag_similarity drive the final score vs. numeric features?

4. Prompt specificity sensitivity
   - More specific prompts → smaller candidate pool (expected)
   - Verify the pipeline degrades gracefully rather than returning empty

5. Edge-case robustness
   - Very vague prompts (should still return a valid tanda)
   - Impossible constraints (should fallback or report cleanly)
   - Unknown orchestra name (should not crash)

Outputs
-------
- Console report per prompt
- eval_04_quality_results.json
- eval_04_quality_summary.csv

Usage
-----
    PYTHONPATH=atdj/rag python3 eval_04_tanda_quality.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]   # tests/test_rag/ → project root
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "atdj" / "rag"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from prompt_to_features import build_translator, load_catalog
from select_tanda import select_tanda

CATALOG_CSV = ROOT / "data" / "reduced_catalog.csv"


# ── Test cases ────────────────────────────────────────────────────────────

QUALITY_CASES = [
    # (prompt, expected_style, expected_decade, notes)
    ("romantic Di Sarli tango from the 1940s, smooth",
     "tango", "1940s", "fully specified"),
    ("fast D'Arienzo tango, very danceable, high energy",
     "tango", None, "no decade constraint"),
    ("lively milonga, fast and playful",
     "milonga", None, "milonga"),
    ("slow melancholic Pugliese tango",
     "tango", None, "mood constraint only"),
    ("classic golden age tango",
     "tango", None, "era-only, no bpm/energy"),
    ("something energetic and fast",
     None, None, "vague - no style"),
    ("calm and relaxing",
     None, None, "very vague"),
    # Edge cases
    ("tango by NonexistentOrchestra 1940",
     "tango", "1940s", "unknown orchestra - should fallback"),
    ("super ultra fast tango 300bpm",
     "tango", None, "impossible bpm - should fallback gracefully"),
]


# ── Analysis helpers ──────────────────────────────────────────────────────

def _score_components(tracks: list[dict]) -> dict:
    """Extract individual score components if they exist."""
    components = ["bpm_score", "danceability_score", "energy_score",
                  "chords_score", "tag_score"]
    result = {}
    for comp in components:
        vals = [t.get(comp) for t in tracks if t.get(comp) is not None]
        if vals:
            result[comp] = dict(
                mean=round(float(np.mean(vals)), 4),
                std=round(float(np.std(vals)), 4),
            )
    return result


def _coherence_metrics(tracks: list[dict], df: pd.DataFrame) -> dict:
    """Measure internal tanda consistency."""
    ids = [t.get("id") or t.get("filename") for t in tracks]
    subset = df[df["id"].isin(ids)] if "id" in df.columns else pd.DataFrame()

    bpm_spread = float("nan")
    energy_spread = float("nan")
    score_variance = float("nan")

    scores = [float(t.get("composite_score", float("nan"))) for t in tracks]
    valid_scores = [s for s in scores if not np.isnan(s)]
    if valid_scores:
        score_variance = round(float(np.var(valid_scores)), 6)

    if not subset.empty:
        if "bpm" in subset.columns:
            bpm_vals = pd.to_numeric(subset["bpm"], errors="coerce").dropna()
            if len(bpm_vals) > 1:
                bpm_spread = round(float(bpm_vals.max() - bpm_vals.min()), 2)
        if "energy" in subset.columns:
            e_vals = pd.to_numeric(subset["energy"], errors="coerce").dropna()
            if len(e_vals) > 1:
                energy_spread = round(float(e_vals.max() - e_vals.min()), 4)

    return dict(
        score_variance=score_variance,
        bpm_spread_bpm=bpm_spread,
        energy_spread=energy_spread,
    )


def _constraint_adherence(bundle_merged: dict, tracks: list[dict]) -> dict:
    """Check that hard constraints in the bundle are honoured by all tanda tracks."""
    checks = {}
    style_req = bundle_merged.get("style")
    if style_req:
        all_match = all(
            str(t.get("style", "")).lower() == style_req.lower()
            for t in tracks
        )
        checks["style_ok"] = all_match

    decade_req = bundle_merged.get("decade")
    if decade_req:
        decade_num = int(str(decade_req).replace("s", "").replace("'", ""))
        all_match = all(
            abs(int(float(t.get("year", decade_num))) // 10 * 10 - decade_num) <= 5
            for t in tracks
            if t.get("year") is not None
        )
        checks["decade_ok"] = all_match

    orch_req = bundle_merged.get("orchestra")
    if orch_req:
        all_match = all(
            orch_req.lower() in str(t.get("orchestra", "")).lower()
            for t in tracks
        )
        checks["orchestra_ok"] = all_match

    return checks


def _run_quality_case(
    prompt: str,
    expected_style: str | None,
    expected_decade: str | None,
    notes: str,
    translator,
    df: pd.DataFrame,
) -> dict:
    t0 = time.perf_counter()
    bundle = translator.translate(prompt)
    translate_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    result = select_tanda(bundle, df)
    select_s = time.perf_counter() - t1

    tracks = result.tanda or []
    merged = bundle.merged or {}
    scores = [float(t.get("composite_score", float("nan"))) for t in tracks]
    valid_scores = [s for s in scores if not np.isnan(s)]

    coherence = _coherence_metrics(tracks, df)
    adherence = _constraint_adherence(merged, tracks)

    # Pool analysis from result.candidates (list of dicts)
    candidates = result.candidates or []
    pool_size = len(candidates)
    if candidates:
        df_cand = pd.DataFrame(candidates)
        style = tracks[0].get("style") if tracks else None
        min_size = 4 if str(style).lower() == "tango" else 3
        if "combo_key" in df_cand.columns:
            eligible = int((df_cand.groupby("combo_key").size() >= min_size).sum())
        else:
            eligible = 0
    else:
        eligible = 0
    pool = dict(candidate_pool_size=pool_size,
                n_combo_keys_with_enough_tracks=eligible)

    components = _score_components(tracks)

    # Interpretability: which fields drove the filter?
    active_hard_fields = [
        k for k, v in merged.items()
        if v not in (None, "", [])
        and k in ("style", "decade", "year", "orchestra", "singer")
    ]
    active_soft_fields = [
        k for k, v in merged.items()
        if v not in (None, "", [])
        and k in ("bpm_label", "danceability_label", "energy_label",
                  "chords_changes_rate_label", "tags")
    ]

    return dict(
        prompt=prompt,
        notes=notes,
        expected_style=expected_style,
        expected_decade=expected_decade,
        translate_s=round(translate_s, 3),
        select_s=round(select_s, 3),
        total_s=round(translate_s + select_s, 3),
        has_tanda=bool(tracks),
        tanda_size=len(tracks),
        mean_score=round(float(np.nanmean(valid_scores)), 4) if valid_scores else float("nan"),
        min_score=round(float(np.nanmin(valid_scores)), 4) if valid_scores else float("nan"),
        max_score=round(float(np.nanmax(valid_scores)), 4) if valid_scores else float("nan"),
        n_active_hard_fields=len(active_hard_fields),
        active_hard_fields=active_hard_fields,
        n_active_soft_fields=len(active_soft_fields),
        active_soft_fields=active_soft_fields,
        constraint_adherence=adherence,
        coherence=coherence,
        pool=pool,
        score_components=components,
        tanda_tracks=[
            {k: t.get(k) for k in
             ("title", "orchestra", "singer", "style", "year", "bpm", "composite_score")}
            for t in tracks
        ],
    )


def _print_case(row: dict, idx: int, total: int) -> None:
    ok = "✓" if row["has_tanda"] else "✗"
    print(f"\n[{idx}/{total}] {ok}  {row['notes'].upper()}")
    print(f"  Prompt: {row['prompt']!r}")
    print(f"  Latency: translate={row['translate_s']:.2f}s  select={row['select_s']:.3f}s  "
          f"total={row['total_s']:.2f}s")
    print(f"  Tanda: size={row['tanda_size']}  "
          f"mean_score={row['mean_score']}  "
          f"score_variance={row['coherence']['score_variance']}")
    print(f"  Pool: {row['pool']['candidate_pool_size']} candidates  "
          f"eligible combo_keys={row['pool']['n_combo_keys_with_enough_tracks']}")
    print(f"  Hard fields active: {row['active_hard_fields']}")
    print(f"  Soft fields active: {row['active_soft_fields']}")
    if row["constraint_adherence"]:
        for k, v in row["constraint_adherence"].items():
            icon = "✓" if v else "✗"
            print(f"  Adherence {icon}  {k}")
    print(f"  BPM spread within tanda: {row['coherence']['bpm_spread_bpm']} bpm")
    if row["tanda_tracks"]:
        print("  Tracks:")
        for t in row["tanda_tracks"]:
            print(f"    {t.get('title','?'):<40} "
                  f"{t.get('orchestra','?'):<20} "
                  f"{t.get('year','')}  "
                  f"bpm={t.get('bpm','')}  "
                  f"score={t.get('composite_score', '?'):.4f}" if isinstance(t.get("composite_score"), float)
                  else f"    {t.get('title','?')} — {t.get('orchestra','?')}")


def _aggregate_quality(rows: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("AGGREGATE QUALITY REPORT")
    print("=" * 60)

    df_r = pd.DataFrame(rows)
    print(f"\nValid tanda rate:         {df_r['has_tanda'].mean():.1%}")
    print(f"Mean score:               {pd.to_numeric(df_r['mean_score'], errors='coerce').mean():.4f}")
    print(f"Mean score variance:      {df_r['coherence'].apply(lambda x: x.get('score_variance', float('nan'))).mean():.6f}")
    print(f"Mean BPM spread:          {df_r['coherence'].apply(lambda x: x.get('bpm_spread_bpm', float('nan'))).mean():.2f} bpm")
    print(f"Mean pool size:           {df_r['pool'].apply(lambda x: x.get('candidate_pool_size', 0)).mean():.0f}")
    print(f"Mean latency:             {df_r['total_s'].mean():.2f}s")

    print("\nConstraint adherence (when constraint present):")
    style_ok = [r["constraint_adherence"].get("style_ok") for r in rows
                if "style_ok" in r["constraint_adherence"]]
    decade_ok = [r["constraint_adherence"].get("decade_ok") for r in rows
                 if "decade_ok" in r["constraint_adherence"]]
    if style_ok:
        print(f"  Style:   {sum(style_ok)}/{len(style_ok)} = {sum(style_ok)/len(style_ok):.0%}")
    if decade_ok:
        print(f"  Decade:  {sum(decade_ok)}/{len(decade_ok)} = {sum(decade_ok)/len(decade_ok):.0%}")

    print("\nPrompt specificity vs pool size:")
    for r in rows:
        n_hard = r["n_active_hard_fields"]
        n_soft = r["n_active_soft_fields"]
        pool = r["pool"]["candidate_pool_size"]
        print(f"  hard={n_hard} soft={n_soft}  → pool={pool:>3}   {r['notes']}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(CATALOG_CSV))
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--quick", action="store_true",
                        help="Run only the first 5 cases")
    parser.add_argument("--model", default=None,
                        help="Override Gemini model name (e.g. gemini-2.0-flash-lite)")
    args = parser.parse_args()

    import os
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
    elif not os.environ.get("GEMINI_MODEL"):
        os.environ["GEMINI_MODEL"] = "gemini-2.0-flash-lite"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading catalog from {args.csv} ...")
    df = load_catalog(args.csv)
    print(f"  {len(df)} tracks.")
    print("Building translator ...")
    translator = build_translator(df)

    cases = QUALITY_CASES[:5] if args.quick else QUALITY_CASES
    print(f"\nRunning {len(cases)} quality cases ...\n")

    all_rows: list[dict] = []
    for i, (prompt, exp_style, exp_decade, notes) in enumerate(cases, 1):
        row = _run_quality_case(prompt, exp_style, exp_decade, notes, translator, df)
        _print_case(row, i, len(cases))
        all_rows.append(row)

    _aggregate_quality(all_rows)

    # ── Save ──────────────────────────────────────────────────────────────
    json_path = out_dir / "eval_04_quality_results.json"
    with open(json_path, "w") as f:
        json.dump(all_rows, f, indent=2, default=str)
    print(f"\n✓ Full results  → {json_path}")

    flat = []
    for r in all_rows:
        flat_row = {k: v for k, v in r.items()
                    if k not in ("constraint_adherence", "coherence", "pool",
                                 "score_components", "tanda_tracks",
                                 "active_hard_fields", "active_soft_fields")}
        flat_row.update({
            f"adherence_{k}": v
            for k, v in r.get("constraint_adherence", {}).items()
        })
        flat_row.update({
            f"coherence_{k}": v
            for k, v in r.get("coherence", {}).items()
        })
        flat_row.update({
            f"pool_{k}": v
            for k, v in r.get("pool", {}).items()
        })
        flat.append(flat_row)

    csv_path = out_dir / "eval_04_quality_summary.csv"
    pd.DataFrame(flat).to_csv(csv_path, index=False)
    print(f"✓ Flat summary  → {csv_path}")


if __name__ == "__main__":
    main()
