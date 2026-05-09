"""
eval_00_run_all.py
==================
Master runner that executes all four evaluation scripts and
produces a combined Markdown summary suitable for pasting into the
project report or presentation.

Evals run
---------
  eval_01_pipeline_comparison.py  — our method vs COT
  eval_02_qa_accuracy_latency.py  — Q&A accuracy + latency
  eval_03_caching_benchmark.py    — cache speedup across all layers
  eval_04_tanda_quality.py        — tanda quality deep-dive

Usage
-----
    # Run from the project root
    PYTHONPATH=atdj/rag python3 tests/eval_00_run_all.py

    # Quick mode (small prompt sets, faster)
    PYTHONPATH=atdj/rag python3 tests/eval_00_run_all.py --quick

    # Skip evals that need the live LLM (CI-friendly)
    PYTHONPATH=atdj/rag python3 tests/eval_00_run_all.py --no-llm

Outputs
-------
  eval_outputs/eval_01_results.json
  eval_outputs/eval_02_qa_results.json
  eval_outputs/eval_03_cache_results.json
  eval_outputs/eval_04_quality_results.json
  eval_outputs/eval_summary.md      ← report-ready Markdown
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
ROOT = THIS_FILE.parents[1]          # project root (tests/ is one level up)
EVAL_DIR = THIS_FILE.parent / "test_rag"  # where eval_01-04 live
OUT_DIR = ROOT / "eval_outputs"


def _make_env() -> dict:
    """
    Build a subprocess environment that:
    - inherits everything from the current process (API keys, LLM_PROVIDER, GEMINI_MODEL, etc.)
    - sets PYTHONPATH so both `atdj.xxx` and bare `rag` module imports work.
    """
    import os
    env = os.environ.copy()
    # Need both the project root (for `from atdj.config import ...`)
    # and atdj/rag (for bare `from prompt_to_features import ...`)
    existing = env.get("PYTHONPATH", "")
    extra = f"{ROOT}{os.pathsep}{ROOT / 'atdj' / 'rag'}"
    env["PYTHONPATH"] = f"{extra}{os.pathsep}{existing}" if existing else extra
    return env


def _run_eval(script: str, extra_args: list[str]) -> bool:
    """Run a single eval script as a subprocess. Returns True on success."""
    cmd = [sys.executable, str(EVAL_DIR / script),
           "--out-dir", str(OUT_DIR)] + extra_args
    print(f"\n{'='*60}")
    print(f"  Running: {script}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, env=_make_env())
    if result.returncode != 0:
        print(f"  [WARN] {script} exited with code {result.returncode}")
        return False
    return True


def _load_json(path: Path) -> list | dict | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _generate_markdown_summary(out_dir: Path) -> str:
    lines = [
        f"# AT-DJ Evaluation Summary",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # ── Eval 01: Pipeline comparison ─────────────────────────────────────
    lines.append("## 1. Pipeline Comparison: Our Method vs COT")
    data = _load_json(out_dir / "eval_01_results.json")
    if data:
        import pandas as pd
        df = pd.DataFrame(data)
        # All rows are now our_pipeline only
        scores = pd.to_numeric(df.get("mean_tanda_score", pd.Series()), errors="coerce").dropna()
        latencies = pd.to_numeric(df.get("total_latency_s", pd.Series()), errors="coerce").dropna()

        lines.append("\n### Our Pipeline")
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| n prompts | {len(df)} |")
        if len(latencies):
            lines.append(f"| Mean latency (s) | {latencies.mean():.2f} |")
            lines.append(f"| Min latency (s) | {latencies.min():.2f} |")
            lines.append(f"| Max latency (s) | {latencies.max():.2f} |")
        if len(scores):
            lines.append(f"| Mean tanda score | {scores.mean():.4f} |")
            lines.append(f"| Min tanda score | {scores.min():.4f} |")
            lines.append(f"| Max tanda score | {scores.max():.4f} |")
        for flag in ["valid_combo", "valid_size", "valid_style", "has_tanda"]:
            if flag in df.columns:
                rate = df[flag].apply(lambda x: bool(x)).mean()
                lines.append(f"| {flag} pass rate | {rate:.0%} |")

        lines.append("\n### COT Method (static results from 02c notebook, n=7)")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append("| Mean latency (s) | 8.90 |")
        lines.append("| Min / Max latency (s) | 6.27 / 14.93 |")
        lines.append("| has_tanda pass rate | 100% |")
        lines.append("| valid_combo pass rate | 100% |")
        lines.append("| valid_size pass rate | 100% |")
        lines.append("| Mean tanda score* | 0.970 |")
        lines.append("| Features selected (mean) | 6.4 of 53 available |")
        lines.append("| Out-of-bounds range rate | 25% |")
        lines.append("| Catalog coverage | 58% |")
        lines.append("")
        lines.append("\\* COT scores use raw Essentia feature proximity (~0.88–1.0 range). "
                     "Our scores use a weighted label+tag composite (0–1 range). "
                     "These are **not directly comparable**.")

        lines.append("\n### Head-to-Head on Comparable Metrics")
        lines.append("| Metric | Our Pipeline | COT (02c) |")
        lines.append("|---|---|---|")
        mean_lat = latencies.mean() if len(latencies) else float("nan")
        lines.append(f"| Mean latency (s) | {mean_lat:.2f} | 8.90 |")
        lines.append(f"| has_tanda rate | {df['has_tanda'].apply(bool).mean():.0%} | 100% |")
        lines.append(f"| valid_combo rate | {df['valid_combo'].apply(bool).mean():.0%} | 100% |")
        lines.append(f"| Features used | 5 composite dims | 6.4 raw Essentia |")
        lines.append(f"| Out-of-bounds | N/A (label-based) | 25% |")
        lines.append(f"| Scoring transparency | Named labels → UI | Raw numeric ranges |")
    else:
        lines.append("_Results not available (eval_01 may not have run)_")

    lines.append("")

    # ── Eval 02: Q&A ─────────────────────────────────────────────────────
    lines.append("\n## 2. Q&A Accuracy and Latency")
    data = _load_json(out_dir / "eval_02_qa_results.json")
    if data:
        import pandas as pd
        df = pd.DataFrame(data)
        lines.append(f"\n| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Total cases | {len(df)} |")
        pr = pd.to_numeric(df["pass_rate"], errors="coerce")
        hr = pd.to_numeric(df["hallucination_rate"], errors="coerce")
        lat = pd.to_numeric(df["latency_s"], errors="coerce")
        lines.append(f"| Overall pass rate | {pr.mean():.1%} |")
        lines.append(f"| Hallucination rate | {hr.mean():.1%} |")
        lines.append(f"| Mean latency (s) | {lat.mean():.2f} |")
        lines.append(f"| p90 latency (s) | {lat.quantile(0.9):.2f} |")
        lines.append(f"| Max latency (s) | {lat.max():.2f} |")

        lines.append("\n| Category | Pass Rate | Mean Latency (s) |")
        lines.append("|---|---|---|")
        for cat, grp in df.groupby("category"):
            p = pd.to_numeric(grp["pass_rate"], errors="coerce").mean()
            l = pd.to_numeric(grp["latency_s"], errors="coerce").mean()
            lines.append(f"| {cat} | {p:.0%} | {l:.2f} |")
    else:
        lines.append("_Results not available_")

    # ── Eval 03: Caching ──────────────────────────────────────────────────
    lines.append("\n## 3. Caching Benchmark")
    data = _load_json(out_dir / "eval_03_cache_results.json")
    if data:
        lines.append("\n| Cache Layer | Cold (s) | Warm (s) | Speedup | Saved (ms) |")
        lines.append("|---|---|---|---|---|")
        for r in data:
            layer = r.get("layer", "?")
            cold = r.get("cold_s", float("nan"))
            warm = r.get("warm_s", float("nan"))
            speedup = r.get("speedup_x", float("nan"))
            saved = r.get("saved_ms", float("nan"))
            lines.append(f"| {layer} | {cold:.4f} | {warm:.6f} | {speedup:.0f}× | {saved:.1f} |")
        # Total saved (excluding e2e)
        total_saved = sum(
            r.get("saved_ms", 0) for r in data
            if r.get("layer") != "e2e_pipeline"
        )
        lines.append(f"\n**Total latency saved per warm request (A+B+C+D): "
                     f"{total_saved:.0f} ms ≈ {total_saved/1000:.2f} s**")
    else:
        lines.append("_Results not available_")

    # ── Eval 04: Tanda quality ────────────────────────────────────────────
    lines.append("\n## 4. Tanda Quality Deep-Dive")
    data = _load_json(out_dir / "eval_04_quality_results.json")
    if data:
        import pandas as pd, numpy as np
        df = pd.DataFrame(data)
        valid_rate = df["has_tanda"].mean()
        mean_score = pd.to_numeric(df["mean_score"], errors="coerce").mean()
        lines.append(f"\n| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Valid tanda rate | {valid_rate:.0%} |")
        lines.append(f"| Mean composite score | {mean_score:.4f} |")

        score_var = df["coherence"].apply(
            lambda x: x.get("score_variance", float("nan")) if isinstance(x, dict) else float("nan")
        )
        bpm_spread = df["coherence"].apply(
            lambda x: x.get("bpm_spread_bpm", float("nan")) if isinstance(x, dict) else float("nan")
        )
        lines.append(f"| Mean score variance (lower = more coherent) | {score_var.mean():.6f} |")
        lines.append(f"| Mean BPM spread within tanda | {bpm_spread.mean():.2f} bpm |")

        lines.append("\n| Prompt | Style ✓ | Decade ✓ | Pool | Score | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for r in data:
            adh = r.get("constraint_adherence", {})
            style_ok = "✓" if adh.get("style_ok", None) is True else (
                "—" if "style_ok" not in adh else "✗")
            decade_ok = "✓" if adh.get("decade_ok", None) is True else (
                "—" if "decade_ok" not in adh else "✗")
            pool_n = r.get("pool", {}).get("candidate_pool_size", "?")
            score = r.get("mean_score", "?")
            score_str = f"{score:.4f}" if isinstance(score, float) else str(score)
            prompt_short = r["prompt"][:45] + "…" if len(r["prompt"]) > 45 else r["prompt"]
            lines.append(f"| {prompt_short} | {style_ok} | {decade_ok} | {pool_n} | {score_str} | {r.get('notes','')} |")
    else:
        lines.append("_Results not available_")

    lines.append("\n---")
    lines.append("_Generated by eval_00_run_all.py_")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Pass --quick to each sub-eval")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip evals that require live LLM calls (01, 02, 04)")
    parser.add_argument("--only-summary", action="store_true",
                        help="Skip running evals; just regenerate Markdown from existing JSON")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    quick_args = ["--quick"] if args.quick else []

    if not args.only_summary:
        if not args.no_llm:
            _run_eval("eval_01_pipeline_comparison.py", quick_args)
            _run_eval("eval_02_qa_accuracy_latency.py", quick_args)
        # eval_03 has no --quick flag; in quick mode skip the slow e2e benchmark
        eval03_args = ["--skip-e2e", "--skip-embedding"] if args.quick else ["--skip-embedding"]
        _run_eval("eval_03_caching_benchmark.py", eval03_args)
        if not args.no_llm:
            _run_eval("eval_04_tanda_quality.py", quick_args)

    print(f"\n{'='*60}")
    print("  Generating Markdown summary ...")
    print(f"{'='*60}")
    md = _generate_markdown_summary(OUT_DIR)
    md_path = OUT_DIR / "eval_summary.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"\n✓ Markdown summary → {md_path}")
    print()
    print(md[:2000])
    if len(md) > 2000:
        print(f"\n... (truncated; see {md_path} for full output)")


if __name__ == "__main__":
    main()
