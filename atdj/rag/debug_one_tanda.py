"""
debug_pipeline.py
-----------------
End-to-end debug of the AT-DJ tanda selection pipeline.

Shows every step:
  0. Load catalog
  1. Prompt → Layer 1 (regex: year / decade)
  2. Prompt → Layer 2 (LLM: all other fields)
  3. Merged bundle
  4. Hard filter  (style, decade, orchestra, singer, album, year)
  5. Soft filter  (bpm_label, danceability_label, key, energy_label, chords)
  6. Scoring      (per-feature + composite)
  7. Tanda grouping + best combo

Usage (from rag folder):
    python debug_one_tanda.py --prompt "energetic D'Arienzo tango, fast and danceable"
    python debug_one_tanda.py --prompt "romantic vals 1940s" --provider claude
    python debug_one_tanda.py --prompt "..." --csv ../../data/reduced_catalog.csv --top 15

If you don't have an LLM key configured you can still run with a fixed bundle:
    python debug_pipeline.py --fixed-merged '{"style":"tango","bpm_label":"fast","danceability_label":"high","energy_label":"high","chords_changes_rate":"moderate","tags":["energetic","intense","driving","percussive","powerful"]}'
"""

from __future__ import annotations

import argparse
import ast
import itertools
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# ── Constants (mirrors select_tanda.py) ──────────────────────────────────

LABEL_PERCENTILE = {
    "slow":      0.25,
    "low":       0.25,
    "moderate":  0.50,
    "fast":      0.75,
    "high":      0.75,
    "very fast": 0.90,
}

WEIGHTS = {
    "bpm":          0.20,
    "danceability": 0.20,
    "chords":       0.15,
    "energy":       0.20,
    "tags":         0.25,
}

TANDA_SIZE: dict[str, int] = {
    "tango":   4,
    "vals":    3,
    "milonga": 3,
}
DEFAULT_TANDA_SIZE = 4

SEP  = "─" * 72
SEP2 = "═" * 72


# ── Helpers ───────────────────────────────────────────────────────────────

def _parse_tags(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(t).strip().lower() for t in raw if str(t).strip()]
    if not isinstance(raw, str) or not raw.strip():
        return []
    raw = raw.strip()
    if raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(t).strip().lower() for t in parsed if str(t).strip()]
        except Exception:
            pass
    return [t.strip().lower() for t in raw.split(",") if t.strip()]


def _numeric_score(target_label, track_value: float, feat_min: float, feat_max: float) -> float:
    """Score how close track_value is to the percentile implied by target_label."""
    if not target_label:
        return 0.5
    pct = LABEL_PERCENTILE.get(str(target_label).lower().strip())
    if pct is None:
        return 0.5
    feat_range = feat_max - feat_min
    if feat_range == 0:
        return 1.0
    target_value = feat_min + pct * feat_range
    return float(np.clip(1.0 - abs(track_value - target_value) / feat_range, 0.0, 1.0))


def _jaccard(q: list[str], t: list[str]) -> float:
    qs, ts = set(q), set(t)
    return len(qs & ts) / len(qs | ts) if qs | ts else 0.0


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _tanda_size_for(style) -> int:
    return TANDA_SIZE.get(str(style).lower() if style else "", DEFAULT_TANDA_SIZE)


# ── Step 0: Load catalog ──────────────────────────────────────────────────

def step0_load(csv_path: str) -> tuple[pd.DataFrame, float]:
    t0 = time.perf_counter()
    print(f"\n{SEP2}")
    print("STEP 0 — Load catalog")
    print(SEP2)

    df = pd.read_csv(csv_path)
    print(f"  Rows : {len(df)}")
    print(f"  Cols : {len(df.columns)}")
    print(f"  Columns: {list(df.columns)}")

    # Detect chords column
    for col in ["chords_changes_rate_label", "chords_changes_rate"]:
        if col in df.columns:
            sample = df[col].dropna().iloc[0]
            note = "← label col (used for soft-filter)" if "label" in col else "← raw float (used for scoring)"
            print(f"  {col}: sample={sample!r}  {note}")

    style_counts = df["style"].value_counts().to_dict() if "style" in df.columns else {}
    print(f"  Style distribution: {style_counts}")
    elapsed = time.perf_counter() - t0
    print(f"\n  ⏱  Step 0 elapsed: {elapsed:.3f}s")
    print()
    return df, elapsed


# ── Step 1 & 2: Prompt → merged bundle (via LLM or fixed) ─────────────────

def step1_translate(prompt: str, df: pd.DataFrame, provider: str) -> tuple[dict, float]:
    """Run the two-layer prompt translation and return merged dict."""
    t0 = time.perf_counter()
    print(f"\n{SEP2}")
    print("STEP 1 — Layer 1: regex extraction (year / decade)")
    print(SEP2)

    import re
    decade_match = re.search(r"(?<!\d)(1[89]\d|20\d)0s?(?!\d)", prompt)
    decade = f"{decade_match.group(1)}0s" if decade_match else None

    year_match = re.search(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d|s)", prompt)
    year = int(year_match.group(1)) if year_match else None

    print(f"  Prompt : {prompt!r}")
    print(f"  → year   = {year}")
    print(f"  → decade = {decade}")

    print(f"\n{SEP2}")
    print(f"STEP 2 — Layer 2: LLM extraction  (provider={provider!r})")
    print(SEP2)

    try:
        # Attempt to import from the project's own module
        sys.path.insert(0, str(Path(__file__).parent))
        from prompt_to_features import build_translator, load_catalog as _lc

        translator = build_translator(df, provider=provider)
        bundle = translator.translate(prompt)

        print("  Layer 1 result:")
        print(f"    year   = {bundle.layer1.year}")
        print(f"    decade = {bundle.layer1.decade}")
        print("\n  Layer 2 result (LLM):")
        from dataclasses import asdict
        for k, v in asdict(bundle.layer2).items():
            print(f"    {k:<25} = {v!r}")
        print("\n  Merged bundle:")
        for k, v in bundle.merged.items():
            print(f"    {k:<25} = {v!r}")
        elapsed = time.perf_counter() - t0
        print(f"\n  ⏱  Steps 1+2 elapsed: {elapsed:.3f}s")
        return bundle.merged, elapsed

    except Exception as exc:
        print(f"  ⚠  Could not call LLM translator: {exc.__class__.__name__}: {exc}")
        print("  → Falling back to regex-only bundle (all LLM fields = None).")
        merged = {
            "year": year, "decade": decade,
            "orchestra": None, "singer": None, "style": None, "album": None,
            "bpm_label": "moderate", "danceability_label": "moderate",
            "key": None, "chords_changes_rate": "moderate",
            "energy_label": "moderate",
            "tags": [],
        }
        print(f"\n  Fallback merged: {json.dumps(merged, indent=4)}")
        elapsed = time.perf_counter() - t0
        print(f"\n  ⏱  Steps 1+2 elapsed: {elapsed:.3f}s")
        return merged, elapsed


# ── Step 3: Hard filter ───────────────────────────────────────────────────

def step3_hard_filter(df: pd.DataFrame, merged: dict) -> tuple[pd.DataFrame, float]:
    t0 = time.perf_counter()
    print(f"\n{SEP2}")
    print("STEP 3 — Hard filter  (style, decade, orchestra, singer, album, year)")
    print(SEP2)

    current = df.copy()
    filter_fields = [
        ("style",     "style"),
        ("decade",    "decade"),
        ("orchestra", "orchestra"),
        ("singer",    "singer"),
        ("album",     "album"),
    ]
    for field, col in filter_fields:
        val = merged.get(field)
        if val is None:
            print(f"  [{field}]  skipped (null)")
            continue
        if col not in current.columns:
            print(f"  [{field}]  skipped (column '{col}' missing)")
            continue
        before = len(current)
        mask = current[col].astype(str).str.strip().str.lower() == str(val).lower()
        current = current[mask]
        after = len(current)
        status = "✓" if after > 0 else "✗ KILLS ALL TRACKS"
        print(f"  [{field}={val!r}]  {before} → {after}  {status}")

    year_val = merged.get("year")
    if year_val is not None and merged.get("decade") is None:
        before = len(current)
        try:
            mask = current["year"].fillna(-1).astype(int) == int(year_val)
            current = current[mask]
        except Exception:
            pass
        print(f"  [year={year_val}]  {before} → {len(current)}")

    print(f"\n  ✦ Hard filter result: {len(current)} tracks")
    if len(current) == 0:
        print("  ⚠  All tracks filtered out — tanda selection will fail.")
    elif len(current) <= 10:
        print("  Remaining tracks:")
        for _, r in current.iterrows():
            print(f"    {r.get('title','?'):<35} | {r.get('orchestra','?'):<20} | {r.get('decade','?')}")
    elapsed = time.perf_counter() - t0
    print(f"\n  ⏱  Step 3 elapsed: {elapsed:.3f}s")
    print()
    return current, elapsed


# ── Step 4: Soft filter ───────────────────────────────────────────────────

def step4_soft_filter(hard: pd.DataFrame, merged: dict) -> tuple[pd.DataFrame, bool, float]:
    t0 = time.perf_counter()
    print(f"\n{SEP2}")
    print("STEP 4 — Soft filter  (bpm_label, danceability_label, key, energy_label, chords)")
    print(SEP2)

    if len(hard) == 0:
        print("  Hard filter pool is empty — skipping soft filter.")
        elapsed = time.perf_counter() - t0
        print(f"\n  ⏱  Step 4 elapsed: {elapsed:.3f}s")
        return hard, False, elapsed

    prompt_style = merged.get("style")
    tanda_n = _tanda_size_for(prompt_style)
    print(f"  Style={prompt_style!r} → tanda size needed = {tanda_n}")

    current = hard.copy()
    soft_fields = [
        ("bpm_label",          "bpm_label"),
        ("danceability_label", "danceability_label"),
        ("key",                "key"),
        ("energy_label",       "energy_label"),
    ]
    for field, col in soft_fields:
        val = merged.get(field)
        if val is None:
            print(f"  [{field}]  skipped (null)")
            continue
        if col not in current.columns:
            print(f"  [{field}]  skipped (column '{col}' missing)")
            continue
        before = len(current)
        mask = current[col].astype(str).str.strip().str.lower() == str(val).lower()
        current = current[mask]
        after = len(current)
        status = "✓" if after > 0 else "✗ KILLS ALL"
        print(f"  [{field}={val!r}]  {before} → {after}  {status}")

    ccr = merged.get("chords_changes_rate")
    if ccr is not None:
        col = ("chords_changes_rate_label"
               if "chords_changes_rate_label" in current.columns
               else "chords_changes_rate")
        before = len(current)
        mask = current[col].astype(str).str.strip().str.lower() == str(ccr).lower()
        current = current[mask]
        print(f"  [chords_changes_rate={ccr!r} via '{col}']  {before} → {len(current)}")

    print(f"\n  ✦ Soft filter result: {len(current)} tracks")

    # Check if any combo_key group is viable
    def _has_viable_group(pool: pd.DataFrame) -> bool:
        if "combo_key" not in pool.columns:
            return len(pool) >= tanda_n
        for _, grp in pool.groupby("combo_key"):
            gs = grp["style"].iloc[0] if "style" in grp.columns else None
            needed = tanda_n if prompt_style else _tanda_size_for(gs)
            if len(grp) >= needed:
                return True
        return False

    used_soft = _has_viable_group(current)
    if used_soft:
        print(f"  → CASE A: soft pool has viable group(s). Using soft pool.")
        pool = current
    else:
        print(f"  → CASE B: no viable group in soft pool. Falling back to hard pool ({len(hard)} tracks).")
        pool = hard

    print()
    elapsed = time.perf_counter() - t0
    print(f"  ⏱  Step 4 elapsed: {elapsed:.3f}s\n")
    return pool, used_soft, elapsed


# ── Step 5: Scoring ───────────────────────────────────────────────────────

def step5_score(pool: pd.DataFrame, merged: dict, catalog_df: pd.DataFrame, top_n: int = 15) -> tuple[pd.DataFrame, float]:
    t0 = time.perf_counter()
    print(f"\n{SEP2}")
    print("STEP 5 — Scoring  (numeric feature proximity + tag similarity)")
    print(SEP2)
    print(f"  Weights          : {WEIGHTS}")
    print(f"  Label→percentile : {LABEL_PERCENTILE}")

    def _range(col):
        vals = catalog_df[col].dropna().astype(float)
        return float(vals.min()), float(vals.max())

    bpm_min,    bpm_max    = _range("bpm")
    dance_min,  dance_max  = _range("danceability")
    chord_min,  chord_max  = _range("chords_changes_rate")
    energy_min, energy_max = _range("energy")

    print(f"\n  Catalog feature ranges (used for scoring):")
    print(f"    bpm                : [{bpm_min:.2f},  {bpm_max:.2f}]")
    print(f"    danceability       : [{dance_min:.4f}, {dance_max:.4f}]")
    print(f"    chords_changes_rate: [{chord_min:.4f}, {chord_max:.4f}]")
    print(f"    energy             : [{energy_min:.4f}, {energy_max:.4f}]")

    print(f"\n  Numeric targets derived from labels:")
    for feat, lkey, fmin, fmax in [
        ("bpm",          "bpm_label",          bpm_min,    bpm_max),
        ("danceability", "danceability_label",  dance_min,  dance_max),
        ("chords",       "chords_changes_rate", chord_min,  chord_max),
        ("energy",       "energy_label",        energy_min, energy_max),
    ]:
        lbl = merged.get(lkey)
        if lbl:
            pct = LABEL_PERCENTILE.get(str(lbl).lower(), 0.5)
            target = fmin + pct * (fmax - fmin)
            print(f"    {feat:<20} label={lbl!r:<12} → p{int(pct*100):02d} = {target:.4f}")
        else:
            print(f"    {feat:<20} label=None → score defaults to 0.5")

    # Tag similarity
    query_tags = [t.lower() for t in merged.get("tags", [])]
    print(f"\n  Query tags: {query_tags}")

    use_st = False
    st_model = None
    q_vec = None
    try:
        from sentence_transformers import SentenceTransformer
        st_model = SentenceTransformer("all-MiniLM-L6-v2")
        q_vec = st_model.encode(" ".join(query_tags), normalize_embeddings=True)
        use_st = True
        print("  sentence-transformers: AVAILABLE ✓ (using cosine similarity)")
    except ImportError:
        print("  sentence-transformers: not installed → using Jaccard fallback")
    except Exception as e:
        print(f"  sentence-transformers: failed ({e.__class__.__name__}) → using Jaccard fallback")

    def tag_sim(track_tags: list[str]) -> float:
        if use_st and st_model and q_vec is not None:
            if not track_tags:
                return 0.0
            t_vec = st_model.encode(" ".join(track_tags), normalize_embeddings=True)
            return _cosine(q_vec, t_vec)
        return _jaccard(query_tags, track_tags)

    records = []
    for _, row in pool.iterrows():
        track_tags = _parse_tags(row.get("tags", ""))
        bpm_s = _numeric_score(merged.get("bpm_label"),
                               float(row.get("bpm") or 0), bpm_min, bpm_max)
        dan_s = _numeric_score(merged.get("danceability_label"),
                               float(row.get("danceability") or 0), dance_min, dance_max)
        crd_s = _numeric_score(merged.get("chords_changes_rate"),
                               float(row.get("chords_changes_rate") or 0), chord_min, chord_max)
        eng_s = _numeric_score(merged.get("energy_label"),
                               float(row.get("energy") or 0), energy_min, energy_max)
        tag_s = tag_sim(track_tags)
        comp  = (WEIGHTS["bpm"]          * bpm_s
               + WEIGHTS["danceability"] * dan_s
               + WEIGHTS["chords"]       * crd_s
               + WEIGHTS["energy"]       * eng_s
               + WEIGHTS["tags"]         * tag_s)
        records.append({
            **row.to_dict(),
            "bpm_score": bpm_s, "danceability_score": dan_s,
            "chords_score": crd_s, "energy_score": eng_s,
            "tag_sim": tag_s, "composite_score": comp,
        })

    scored = pd.DataFrame(records).sort_values("composite_score", ascending=False)

    print(f"\n  Top {top_n} candidates (sorted by composite score):")
    print(f"  {'Title':<35} {'Orchestra':<22} {'Combo key':<30}  bpm  dan  crd  eng  tag  → comp")
    print("  " + "─" * 120)
    for _, r in scored.head(top_n).iterrows():
        print(
            f"  {str(r.get('title','')):<35} {str(r.get('orchestra','')):<22} "
            f"{str(r.get('combo_key','')):<30}  "
            f"{r['bpm_score']:.2f} {r['danceability_score']:.2f} "
            f"{r['chords_score']:.2f} {r['energy_score']:.2f} {r['tag_sim']:.2f}  "
            f"→ {r['composite_score']:.4f}"
        )
    elapsed = time.perf_counter() - t0
    print(f"  ⏱  Step 5 elapsed: {elapsed:.3f}s\n")
    return scored, elapsed


# ── Step 6: Tanda grouping ────────────────────────────────────────────────

def step6_tanda(scored: pd.DataFrame, merged: dict) -> float:
    t0 = time.perf_counter()
    print(f"\n{SEP2}")
    print("STEP 6 — Tanda grouping + best combination")
    print(SEP2)

    if len(scored) == 0:
        print("  Pool is empty — no tanda can be formed.")
        elapsed = time.perf_counter() - t0
        print(f"\n  ⏱  Step 6 elapsed: {elapsed:.3f}s")
        return elapsed

    prompt_style = merged.get("style")
    tanda_n = _tanda_size_for(prompt_style)
    print(f"  Style={prompt_style!r} → tanda size = {tanda_n}")

    if "combo_key" not in scored.columns:
        print("  ERROR: 'combo_key' column missing — cannot group by combo_key.")
        elapsed = time.perf_counter() - t0
        print(f"\n  ⏱  Step 6 elapsed: {elapsed:.3f}s")
        return elapsed

    # Show all groups
    print(f"\n  All combo_key groups in scored pool:")
    for ck, grp in scored.groupby("combo_key"):
        n_needed = tanda_n if prompt_style else _tanda_size_for(
            grp["style"].iloc[0] if "style" in grp.columns else None
        )
        eligible = "✓ eligible" if len(grp) >= n_needed else f"✗ only {len(grp)} track(s), need {n_needed}"
        top_scores = list(grp["composite_score"].round(4).head(5))
        print(f"    {str(ck):<40}  {len(grp):>3} tracks  {eligible}")
        print(f"      top scores: {top_scores}")

    # Find best tanda
    best_mean, best_tanda, best_key = -1.0, [], ""
    for ck, group in scored.groupby("combo_key"):
        n_needed = tanda_n if prompt_style else _tanda_size_for(
            group["style"].iloc[0] if "style" in group.columns else None
        )
        if len(group) < n_needed:
            continue
        pool = group.head(20)
        for idxs in itertools.combinations(range(len(pool)), n_needed):
            rows = pool.iloc[list(idxs)]
            m = rows["composite_score"].mean()
            if m > best_mean:
                best_mean = m
                best_tanda = rows.to_dict("records")
                best_key = str(ck)

    print()
    if not best_tanda:
        print("  ✗ No valid tanda found. No combo_key group had enough tracks.")
        elapsed = time.perf_counter() - t0
        print(f"\n  ⏱  Step 6 elapsed: {elapsed:.3f}s")
        return elapsed

    print(f"  ★ BEST TANDA  combo_key={best_key!r}  mean_score={best_mean:.4f}")
    print()
    for i, t in enumerate(best_tanda, 1):
        print(
            f"  {i}. {str(t.get('title','?')):<38} | {str(t.get('orchestra','?')):<22}"
            f" | {t.get('decade','?')}"
            f" | bpm={t.get('bpm_label','?'):<10}"
            f" dance={t.get('danceability_label','?'):<10}"
            f" energy={t.get('energy_label','?'):<10}"
            f" score={t['composite_score']:.4f}"
        )
    elapsed = time.perf_counter() - t0
    print(f"\n  ⏱  Step 6 elapsed: {elapsed:.3f}s")
    print()
    return elapsed


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AT-DJ debug pipeline: prompt → features → scoring → tanda"
    )
    parser.add_argument("--prompt", "-p", default=None,
                        help="Natural-language DJ prompt (required unless --fixed-merged is used)")
    parser.add_argument("--csv", default="../../data/reduced_catalog.csv",
                        help="Path to reduced_catalog.csv (default: ../../data/reduced_catalog.csv)")
    parser.add_argument("--provider", default=None,
                        help="LLM provider: openai | claude | gemini (overrides LLM_PROVIDER env var)")
    parser.add_argument("--fixed-merged", default=None,
                        help="JSON string with a pre-built merged dict (skips LLM translation)")
    parser.add_argument("--top", type=int, default=15,
                        help="How many top candidates to print in scoring step (default: 15)")
    args = parser.parse_args()

    if args.prompt is None and args.fixed_merged is None:
        parser.error("Provide either --prompt or --fixed-merged.")

    provider = args.provider or os.getenv("LLM_PROVIDER", "gemini")

    print(f"\n{SEP2}")
    print("AT-DJ  end-to-end debug pipeline")
    print(SEP2)
    if args.prompt:
        print(f"  Prompt   : {args.prompt!r}")
    print(f"  CSV      : {args.csv}")
    print(f"  Provider : {provider}")
    print(f"  Top-N    : {args.top}")

    wall_start = time.perf_counter()

    # Step 0
    df, t0 = step0_load(args.csv)

    # Steps 1+2 (or fixed bundle)
    t12 = 0.0
    if args.fixed_merged:
        merged = json.loads(args.fixed_merged)
        print(f"\n{SEP2}")
        print("STEPS 1+2 — Using fixed merged bundle (no LLM)")
        print(SEP2)
        print(json.dumps(merged, indent=2))
    else:
        merged, t12 = step1_translate(args.prompt, df, provider)

    # Steps 3–6
    hard,   t3             = step3_hard_filter(df, merged)
    pool,   used_soft, t4  = step4_soft_filter(hard, merged)
    scored, t5             = step5_score(pool, merged, df, top_n=args.top)
    t6                     = step6_tanda(scored, merged)

    wall = time.perf_counter() - wall_start

    print(SEP2)
    print("⏱  TIMING SUMMARY")
    print(SEP2)
    rows = [
        ("Step 0  load catalog",      t0),
        ("Steps 1+2  prompt → LLM",   t12),
        ("Step 3  hard filter",        t3),
        ("Step 4  soft filter",        t4),
        ("Step 5  scoring",            t5),
        ("Step 6  tanda grouping",     t6 or 0.0),
    ]
    for label, secs in rows:
        bar = "█" * max(1, int(secs / wall * 30))
        print(f"  {label:<30} {secs:>6.3f}s  {bar}")
    print(f"  {'TOTAL (wall clock)':<30} {wall:>6.3f}s")
    print(SEP2)
    print("Done.")
    print(SEP2)


if __name__ == "__main__":
    main()
