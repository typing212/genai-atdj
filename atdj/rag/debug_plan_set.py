"""
debug_plan_set.py
-----------------
End-to-end debug of the full milonga set planner.

Shows every step:
  0.  Load catalog + style inventory
  1.  Prompt → merged bundle  (LLM or fixed)
  2.  Set schema   (style order + tanda sizes)
  3.  Per-slot:
        3a. Pool size after combo_key exclusion
        3b. Hard filter counts per style
        3c. Scoring summary (top 5 candidates)
        3d. Chosen tanda tracks + scores
  4.  Full set summary table
  5.  Sanity checks  (no duplicate combo_keys, styles match schema)

Usage:
    python debug_plan_set.py --prompt "romantic 1940s, smooth and elegant"
    python debug_plan_set.py --prompt "..." --provider claude
    python debug_plan_set.py --prompt "..." --schema tango vals milonga
    python debug_plan_set.py \\
        --fixed-merged '{"style":null,"decade":"1940s","bpm_label":"moderate",
                         "danceability_label":"moderate","energy_label":"moderate",
                         "chords_changes_rate":"moderate","tags":["elegant","smooth",
                         "romantic","nostalgic","lyrical"],
                         "orchestra":null,"singer":null,"album":null,"year":null}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup — support both flat and package layouts
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, _HERE / "atdj" / "rag", Path("atdj/rag")]:
    if (_candidate / "select_tanda.py").exists():
        sys.path.insert(0, str(_candidate))
        break

from select_tanda import (  # noqa: E402
    TandaResult,
    _hard_filter,
    _score_candidates,
    TANDA_SIZE,
    DEFAULT_TANDA_SIZE,
)
from plan_set import plan_set, SetResult, DEFAULT_SET_SCHEMA  # noqa: E402

# ── Formatting helpers ─────────────────────────────────────────────────────

SEP  = "─" * 72
SEP2 = "═" * 72
W    = 72  # print width


def _header(title: str) -> None:
    print(f"\n{SEP2}")
    print(title)
    print(SEP2)


def _sub(title: str) -> None:
    print(f"\n  {SEP[:68]}")
    print(f"  {title}")
    print(f"  {SEP[:68]}")


def _tanda_size(style: str) -> int:
    return TANDA_SIZE.get(style.lower(), DEFAULT_TANDA_SIZE)


# ── Timing ─────────────────────────────────────────────────────────────────

def _fmt(seconds: float) -> str:
    """Human-readable: ms below 1 s, else seconds with 2 dp."""
    if seconds < 1:
        return f"{seconds * 1_000:.1f} ms"
    return f"{seconds:.2f} s"


class Stopwatch:
    """
    Lightweight timing collector.  Use as a context manager per phase:

        sw = Stopwatch()
        with sw("catalog load"):
            df = pd.read_csv(...)

    Call sw.report() at the end to print the table.
    """

    def __init__(self) -> None:
        self._laps: list[tuple[str, float]] = []
        self._wall_start: float = time.perf_counter()
        self._current_label: str = ""
        self._lap_start: float = 0.0

    def __call__(self, label: str) -> "Stopwatch":
        self._current_label = label
        return self

    def __enter__(self) -> "Stopwatch":
        self._lap_start = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        elapsed = time.perf_counter() - self._lap_start
        self._laps.append((self._current_label, elapsed))

    def report(self) -> None:
        total_wall = time.perf_counter() - self._wall_start
        _header("STEP 6 — Timing report")

        col = max(len(label) for label, _ in self._laps) + 2
        bar_max_w = 30
        max_elapsed = max(e for _, e in self._laps) or 1.0

        print(f"  {'Phase':<{col}}  {'Time':>9}  {'% of wall':>9}  Bar")
        print(f"  {'─' * col}  {'─'*9}  {'─'*9}  {'─'*bar_max_w}")

        for label, elapsed in self._laps:
            pct = elapsed / total_wall * 100
            bar_w = max(1, round(elapsed / max_elapsed * bar_max_w))
            bar = "█" * bar_w
            print(f"  {label:<{col}}  {_fmt(elapsed):>9}  {pct:>8.1f}%  {bar}")

        print(f"  {'─' * col}  {'─'*9}  {'─'*9}")
        print(f"  {'TOTAL (wall clock)':<{col}}  {_fmt(total_wall):>9}")
        print()


# ── Step 0: catalog overview ───────────────────────────────────────────────

def step0_catalog(df: pd.DataFrame) -> None:
    _header("STEP 0 — Catalog overview")
    print(f"  Total tracks : {len(df)}")
    print(f"  Total combo_keys : {df['combo_key'].nunique()}")

    print("\n  Style breakdown:")
    for style, grp in df.groupby("style"):
        combo_count = grp["combo_key"].nunique()
        viable = sum(
            1 for _, sg in grp.groupby("combo_key")
            if len(sg) >= _tanda_size(str(style))
        )
        print(f"    {str(style):<10}  {len(grp):>4} tracks  "
              f"{combo_count:>3} combo_keys  "
              f"{viable:>3} viable (≥{_tanda_size(str(style))} tracks)")

    print("\n  Decade breakdown:")
    for decade, cnt in df["decade"].value_counts().sort_index().items():
        print(f"    {decade}  {cnt}")


# ── Step 1: bundle display ─────────────────────────────────────────────────

def step1_bundle(bundle: dict, source: str) -> None:
    _header(f"STEP 1 — Merged feature bundle  ({source})")
    max_k = max(len(k) for k in bundle)
    for k, v in bundle.items():
        print(f"  {k:<{max_k}}  =  {v!r}")


# ── Step 2: schema display ─────────────────────────────────────────────────

def step2_schema(schema: list[str]) -> None:
    _header("STEP 2 — Set schema")
    print(f"  {'Slot':<6}  {'Style':<10}  {'Tanda size'}")
    print(f"  {'─'*6}  {'─'*10}  {'─'*10}")
    for i, style in enumerate(schema, 1):
        print(f"  {i:<6}  {style:<10}  {_tanda_size(style)} tracks")
    print(f"\n  Total tracks in set: "
          f"{sum(_tanda_size(s) for s in schema)}")


# ── Step 3: per-slot verbose output ───────────────────────────────────────

def step3_slots(
    result: SetResult,
    df: pd.DataFrame,
) -> None:
    _header("STEP 3 — Per-slot selection detail")

    used_so_far: list[str] = []

    for slot_idx, (slot, slot_style, chosen_key) in enumerate(
        zip(result.slots, result.set_schema, result.used_combo_keys), start=1
    ):
        _sub(f"Slot {slot_idx}/{len(result.schema)}  —  style: {slot_style.upper()}")

        # ── 3a: pool size ──────────────────────────────────────────────────
        if used_so_far:
            pool = df[~df["combo_key"].isin(used_so_far)]
        else:
            pool = df

        pool_style = pool[pool["style"].str.lower() == slot_style]
        print(f"\n  Pool after exclusion:")
        print(f"    Total tracks (all styles) : {len(pool)}")
        print(f"    Tracks matching '{slot_style}'  : {len(pool_style)}")
        print(f"    Combo_keys excluded so far : {len(used_so_far)}  {used_so_far or '[]'}")

        # ── 3b: hard filter ────────────────────────────────────────────────
        slot_bundle = {**result.base_bundle, "style": slot_style}
        hard = _hard_filter(pool, slot_bundle)
        viable_groups = [
            ck for ck, g in hard.groupby("combo_key")
            if len(g) >= _tanda_size(slot_style)
        ]
        print(f"\n  Hard filter → {len(hard)} tracks  "
              f"({len(viable_groups)} viable combo_key groups):")
        for ck, g in list(hard.groupby("combo_key"))[:8]:
            mark = "✓" if len(g) >= _tanda_size(slot_style) else "✗"
            print(f"    {mark}  {str(ck):<45}  {len(g):>2} tracks")
        if hard.groupby("combo_key").ngroups > 8:
            print(f"    … and {hard.groupby('combo_key').ngroups - 8} more groups")

        # ── 3c: top scoring candidates ─────────────────────────────────────
        if len(hard) > 0:
            try:
                scored = _score_candidates(hard, slot_bundle, df)
                print(f"\n  Top 5 scored candidates (before tanda grouping):")
                print(f"  {'Title':<35} {'Combo key':<35}  bpm  dan  crd  eng  tag → comp")
                print("  " + "─" * 100)
                for _, r in scored.head(5).iterrows():
                    print(
                        f"  {str(r.get('title','')):<35} "
                        f"{str(r.get('combo_key','')):<35}  "
                        f"{r.get('bpm_score',0):.2f} "
                        f"{r.get('danceability_score',0):.2f} "
                        f"{r.get('chords_score',0):.2f} "
                        f"{r.get('energy_score',0):.2f} "
                        f"{r.get('tag_sim',0):.2f} "
                        f"→ {r.get('composite_score',0):.4f}"
                    )
            except Exception as e:
                print(f"  (scoring preview unavailable: {e})")

        # ── 3d: chosen tanda ───────────────────────────────────────────────
        print(f"\n  Result:")
        if slot.tanda:
            print(f"    combo_key  : {chosen_key}")
            print(f"    mean_score : {slot.mean_score:.4f}")
            print(f"    tracks     :")
            for i, t in enumerate(slot.tanda, 1):
                print(
                    f"      {i}. {str(t.get('title','?')):<38}"
                    f"  {str(t.get('orchestra','?')):<22}"
                    f"  {t.get('decade','?')}"
                    f"  score={t.get('composite_score',0):.4f}"
                )
            used_so_far.append(chosen_key)
        else:
            print(f"    ✗  NO TANDA FOUND for this slot")
            used_so_far.append("")


# ── Step 4: full set summary ───────────────────────────────────────────────

def step4_summary(result: SetResult) -> None:
    _header("STEP 4 — Full set summary")

    filled   = sum(1 for s in result.slots if s.tanda)
    failed   = len(result.slots) - filled
    avg_score = (
        sum(s.mean_score for s in result.slots if s.tanda) / filled
        if filled else 0.0
    )

    print(f"  Slots filled : {filled}/{len(result.slots)}")
    print(f"  Slots failed : {failed}")
    print(f"  Avg score    : {avg_score:.4f}")
    print()
    print(f"  {'#':<4} {'Style':<10} {'Combo key':<45} {'Score':<8} {'Tracks'}")
    print(f"  {'─'*4} {'─'*10} {'─'*45} {'─'*8} {'─'*6}")

    for i, (slot, style, ck) in enumerate(
        zip(result.slots, result.set_schema, result.used_combo_keys), start=1
    ):
        if slot.tanda:
            # Show track titles inline
            track_titles = " · ".join(
                str(t.get("title", "?"))[:18] for t in slot.tanda
            )
            print(f"  {i:<4} {style:<10} {ck:<45} {slot.mean_score:<8.4f} {track_titles}")
        else:
            print(f"  {i:<4} {style:<10} {'—':<45} {'FAILED':<8}")

    if result.warnings:
        print("\n  Warnings:")
        for w in result.warnings:
            print(f"    ⚠  {w}")


# ── Step 5: sanity checks ──────────────────────────────────────────────────

def step5_sanity(result: SetResult) -> None:
    _header("STEP 5 — Sanity checks")

    ok = True

    # Check: no duplicate combo_keys
    filled_keys = [k for k in result.used_combo_keys if k]
    if len(filled_keys) == len(set(filled_keys)):
        print("  ✓  No duplicate combo_keys across the set")
    else:
        from collections import Counter
        dupes = [k for k, c in Counter(filled_keys).items() if c > 1]
        print(f"  ✗  Duplicate combo_keys detected: {dupes}")
        ok = False

    # Check: styles match schema
    style_mismatches = []
    for i, (slot, expected_style, ck) in enumerate(
        zip(result.slots, result.set_schema, result.used_combo_keys), start=1
    ):
        if not slot.tanda:
            continue
        actual_style = slot.tanda[0].get("style", "").lower().strip()
        if actual_style != expected_style.lower():
            style_mismatches.append(
                f"Slot {i}: expected '{expected_style}', got '{actual_style}' ({ck})"
            )

    if not style_mismatches:
        print("  ✓  All filled slots match their schema style")
    else:
        for m in style_mismatches:
            print(f"  ✗  Style mismatch: {m}")
        ok = False

    # Check: tanda sizes
    size_issues = []
    for i, (slot, style) in enumerate(zip(result.slots, result.set_schema), start=1):
        if not slot.tanda:
            continue
        expected_n = _tanda_size(style)
        actual_n   = len(slot.tanda)
        if actual_n != expected_n:
            size_issues.append(
                f"Slot {i} ({style}): expected {expected_n} tracks, got {actual_n}"
            )
    if not size_issues:
        print("  ✓  All tanda sizes are correct  "
              "(4 for tango, 3 for vals/milonga)")
    else:
        for s in size_issues:
            print(f"  ✗  Size issue: {s}")
        ok = False

    # Check: no overlapping tracks between tandas
    all_ids: list[str] = []
    overlap = False
    for slot in result.slots:
        for t in slot.tanda:
            tid = str(t.get("filename") or t.get("id") or t.get("title"))
            if tid in all_ids:
                overlap = True
            all_ids.append(tid)
    if not overlap:
        print("  ✓  No individual track appears in more than one tanda")
    else:
        print("  ✗  Duplicate tracks detected across tandas")
        ok = False

    print()
    print(f"  Overall: {'ALL CHECKS PASSED ✓' if ok else 'SOME CHECKS FAILED ✗'}")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AT-DJ debug — full milonga set planner"
    )
    parser.add_argument("--prompt", "-p", default=None,
                        help="Natural-language DJ prompt.")
    parser.add_argument("--fixed-merged", default=None,
                        help="JSON string with a pre-built merged bundle (skips LLM).")
    parser.add_argument("--csv", default="../../data/reduced_catalog.csv",
                        help="Path to reduced_catalog.csv.")
    parser.add_argument("--schema", nargs="+", default=DEFAULT_SET_SCHEMA,
                        metavar="STYLE",
                        help="Style order (default: tango tango vals tango tango milonga)")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "gemini"),
                        help="LLM provider: gemini | claude | openai")
    args = parser.parse_args()

    if args.prompt is None and args.fixed_merged is None:
        parser.error("Provide either --prompt or --fixed-merged.")

    bundle = json.loads(args.fixed_merged) if args.fixed_merged else None
    schema = args.schema

    print(f"\n{SEP2}")
    print("AT-DJ  debug_plan_set — full milonga set planner")
    print(SEP2)
    if args.prompt:
        print(f"  Prompt   : {args.prompt!r}")
    print(f"  CSV      : {args.csv}")
    print(f"  Provider : {args.provider}")
    print(f"  Schema   : {schema}")

    sw = Stopwatch()

    # Load catalog
    with sw("catalog load"):
        df = pd.read_csv(args.csv)

    with sw("catalog overview (step 0)"):
        step0_catalog(df)

    # Translate prompt if needed
    if bundle is not None:
        source = "fixed --fixed-merged argument"
        translation_label = "prompt translation (skipped — fixed bundle)"
        with sw(translation_label):
            pass  # no-op; bundle already parsed
    else:
        source = f"LLM ({args.provider})"
        print(f"\n{SEP2}")
        print("STEP 1 — Translating prompt via LLM …")
        print(SEP2)
        print(f"  Prompt: {args.prompt!r}")
        print(f"  Provider: {args.provider}")
        # plan_set will do the translation internally; we time the whole planner below

    # Run the planner (verbose=False so we control all output ourselves)
    # Time translation + selection separately by splitting the call.
    if bundle is None:
        # Time just the LLM translation step
        from plan_set import _translate_prompt  # noqa: E402
        with sw("prompt translation (LLM)"):
            resolved_bundle = _translate_prompt(args.prompt, df, args.provider)
        with sw("set planning (6 slots)"):
            result = plan_set(
                catalog_df=df,
                base_bundle=resolved_bundle,
                set_schema=schema,
                provider=args.provider,
                verbose=False,
            )
    else:
        resolved_bundle = bundle
        with sw("set planning (6 slots)"):
            result = plan_set(
                catalog_df=df,
                base_bundle=resolved_bundle,
                set_schema=schema,
                provider=args.provider,
                verbose=False,
            )

    # Add schema to result for step3 access
    result.schema = schema  # type: ignore[attr-defined]

    with sw("bundle + schema display (steps 1-2)"):
        step1_bundle(result.base_bundle, source)
        step2_schema(schema)

    with sw("per-slot detail (step 3)"):
        step3_slots(result, df)

    with sw("set summary (step 4)"):
        step4_summary(result)

    with sw("sanity checks (step 5)"):
        step5_sanity(result)

    # Timing report is always last
    sw.report()

    print(f"\n{SEP2}")
    print("Done.")
    print(SEP2)


if __name__ == "__main__":
    main()
