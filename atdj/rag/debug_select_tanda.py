"""
debug_select_tanda.py
---------------------
Step-by-step debug of the tanda selection pipeline.
Uses a fixed merged dict — no LLM calls.

Run from project root:
    python atdj/rag/debug_select_tanda.py --csv data/reduced_catalog.csv
"""

import ast
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CSV_PATH = "data/reduced_catalog.csv"

# Fixed bundle from the failing run — no LLM needed
FIXED_MERGED = {
    "year": None,
    "decade": None,
    "orchestra": None,
    "singer": None,
    "style": "tango",
    "album": None,
    "bpm_label": "fast",
    "danceability_label": "high",
    "key": None,
    "chords_changes_rate": "moderate",
    "energy_label": "high",
    "tags": ["energetic","driving rhythm","percussive","intense","technical"]
}

LABEL_PERCENTILE = {
    "slow": 0.25, "low": 0.25, "moderate": 0.50,
    "fast": 0.75, "high": 0.75, "very fast": 0.90,
}
WEIGHTS = {"bpm": 0.20, "danceability": 0.20, "chords": 0.15, "energy": 0.20, "tags": 0.25}
TANDA_SIZE   = {"tango": 4, "vals": 3, "milonga": 3}

SEP = "─" * 70


# ── helpers ────────────────────────────────────────────────────────────────

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


def _numeric_score(target_label, track_value, feat_min, feat_max) -> float:
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


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── Step 0: load catalog ───────────────────────────────────────────────────

def step0_load(csv_path: str) -> pd.DataFrame:
    print(SEP)
    print("STEP 0 — Load catalog")
    print(SEP)
    df = pd.read_csv(csv_path)
    print(f"  Total rows: {len(df)}")
    print(f"  Columns:    {list(df.columns)}\n")

    # Check which chords column holds labels vs floats
    if "chords_changes_rate_label" in df.columns:
        sample = df["chords_changes_rate_label"].dropna().iloc[0]
        print(f"  chords_changes_rate_label sample: {sample!r}  ← use this for filtering")
    if "chords_changes_rate" in df.columns:
        sample2 = df["chords_changes_rate"].dropna().iloc[0]
        print(f"  chords_changes_rate sample:       {sample2!r}  ← raw float, NOT for filtering\n")
    return df


# ── Step 1: inspect vals in catalog ───────────────────────────────────────

def step1_inspect_vals(df: pd.DataFrame, merged: dict) -> None:
    print(SEP)
    print("STEP 1 — What vals tracks exist in the catalog?")
    print(SEP)

    vals = df[df["style"].str.lower() == "vals"]
    print(f"  Total vals tracks: {len(vals)}")

    for col in ["decade", "bpm_label", "danceability_label", "energy_label", "chords_changes_rate_label"]:
        if col in vals.columns:
            print(f"  {col} distribution:\n    {vals[col].value_counts().to_dict()}")
    print()

    # Cross-tab: show exactly what combos exist for vals + 1940s
    vals_40 = vals[vals["decade"] == "1940s"]
    print(f"  vals + 1940s: {len(vals_40)} tracks")
    if len(vals_40):
        print("  bpm_label × danceability_label × energy_label cross-tab:")
        for _, r in vals_40[["bpm_label","danceability_label","energy_label","chords_changes_rate_label"]].drop_duplicates().iterrows():
            print(f"    bpm={r['bpm_label']:10} dance={r['danceability_label']:10} energy={r['energy_label']:10} chords={r['chords_changes_rate_label']}")
    print()
    print(f"  Prompt wants: bpm={merged['bpm_label']}  dance={merged['danceability_label']}  energy={merged['energy_label']}  chords={merged['chords_changes_rate']}")
    print()


# ── Step 2: hard filter ───────────────────────────────────────────────────

def step2_hard_filter(df: pd.DataFrame, merged: dict) -> pd.DataFrame:
    print(SEP)
    print("STEP 2 — Hard filter  (style, decade, orchestra, singer, album, year)")
    print(SEP)

    current = df.copy()
    for field, col in [
        ("style",     "style"),
        ("decade",    "decade"),
        ("orchestra", "orchestra"),
        ("singer",    "singer"),
        ("album",     "album"),
    ]:
        val = merged.get(field)
        if val is None:
            continue
        before = len(current)
        mask = current[col].astype(str).str.strip().str.lower() == str(val).lower()
        current = current[mask]
        after = len(current)
        status = "✓" if after > 0 else "✗ KILLS ALL"
        print(f"  [{field}={val!r}] {before} → {after} tracks  {status}")

    year_val = merged.get("year")
    if year_val is not None and merged.get("decade") is None:
        before = len(current)
        try:
            mask = current["year"].fillna(-1).astype(int) == int(year_val)
            current = current[mask]
        except Exception:
            pass
        print(f"  [year={year_val}] {before} → {len(current)} tracks")

    print(f"\n  Hard filter result: {len(current)} tracks\n")
    return current


# ── Step 3: soft filter + cascade decision ────────────────────────────────

def step3_soft_filter(df_hard: pd.DataFrame, merged: dict) -> pd.DataFrame:
    print(SEP)
    print("STEP 3 — Soft filter  (bpm_label, danceability_label, key, chords_changes_rate, energy_label)")
    print(SEP)

    prompt_style = merged.get("style")
    n = TANDA_SIZE.get(str(prompt_style).lower() if prompt_style else "", 4)

    current = df_hard.copy()
    for field, col in [
        ("bpm_label",          "bpm_label"),
        ("danceability_label", "danceability_label"),
        ("key",                "key"),
        ("energy_label",       "energy_label"),
    ]:
        val = merged.get(field)
        if val is None:
            continue
        before = len(current)
        mask = current[col].astype(str).str.strip().str.lower() == str(val).lower()
        current = current[mask]
        after = len(current)
        status = "✓" if after > 0 else "✗ KILLS ALL"
        print(f"  [{field}={val!r}] {before} → {after} tracks  {status}")

    ccr = merged.get("chords_changes_rate")
    if ccr is not None:
        col = "chords_changes_rate_label" if "chords_changes_rate_label" in current.columns else "chords_changes_rate"
        before = len(current)
        mask = current[col].astype(str).str.strip().str.lower() == str(ccr).lower()
        current = current[mask]
        print(f"  [chords_changes_rate={ccr!r} via {col}] {before} → {len(current)} tracks")

    print(f"\n  Soft filter result: {len(current)} tracks")

    # Check if any combo_key group has enough tracks
    viable = False
    for ck, grp in current.groupby("combo_key"):
        gs = grp["style"].iloc[0] if "style" in grp.columns else None
        needed = n if prompt_style else TANDA_SIZE.get(str(gs).lower() if gs else "", 4)
        if len(grp) >= needed:
            viable = True
            print(f"  Viable group found: {ck!r} has {len(grp)} tracks (need {needed}) ✓")

    if viable:
        print(f"\n  → CASE A/B: using soft-filtered pool\n")
        return current
    else:
        print(f"  No viable combo_key group (need ≥{n} tracks per group).")
        print(f"  → CASE C: falling back to hard-filter pool ({len(df_hard)} tracks)\n")
        return df_hard


# ── Step 4: tag similarity ─────────────────────────────────────────────────

def step4_tag_similarity(df_sample: pd.DataFrame, merged: dict) -> None:
    print(SEP)
    print("STEP 4 — Tag similarity (Jaccard fallback + optional sentence-transformers)")
    print(SEP)

    query_tags = [t.lower() for t in merged["tags"]]
    print(f"  Query tags: {query_tags}\n")

    # Try sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        q_vec = model.encode(" ".join(query_tags), normalize_embeddings=True)
        use_st = True
        print("  sentence-transformers: AVAILABLE ✓")
    except ImportError:
        use_st = False
        print("  sentence-transformers: NOT installed — using Jaccard\n")
    except Exception as e:
        use_st = False
        print(f"  sentence-transformers: failed to load model ({e.__class__.__name__}) — using Jaccard\n")

    sample = df_sample.head(8)
    print(f"  {'Title':<35} {'Track tags':<50} {'Jaccard':>8}" + ("  {'CosSim':>8}" if use_st else ""))
    print("  " + "─"*100)

    for _, row in sample.iterrows():
        track_tags = _parse_tags(row.get("tags", ""))
        jac = _jaccard(query_tags, track_tags)
        line = f"  {str(row.get('title','')):<35} {str(track_tags):<50} {jac:8.4f}"
        if use_st:
            t_vec = model.encode(" ".join(track_tags), normalize_embeddings=True)
            cos = _cosine_sim(q_vec, t_vec)
            line += f"  {cos:8.4f}"
        print(line)
    print()


# ── Step 5: score every candidate ─────────────────────────────────────────

def step5_score(df: pd.DataFrame, merged: dict, catalog_df: pd.DataFrame) -> pd.DataFrame:
    print(SEP)
    print("STEP 5 — Score every candidate  (numeric feature values, not labels)")
    print(SEP)
    print(f"  Weights: {WEIGHTS}")
    print(f"  Label → percentile: {LABEL_PERCENTILE}\n")

    def _range(col):
        vals = catalog_df[col].dropna().astype(float)
        return float(vals.min()), float(vals.max())

    bpm_min,    bpm_max    = _range("bpm")
    dance_min,  dance_max  = _range("danceability")
    chord_min,  chord_max  = _range("chords_changes_rate")
    energy_min, energy_max = _range("energy")

    print(f"  Catalog feature ranges:")
    print(f"    bpm:                [{bpm_min:.2f},  {bpm_max:.2f}]")
    print(f"    danceability:       [{dance_min:.4f}, {dance_max:.4f}]")
    print(f"    chords_changes_rate:[{chord_min:.4f}, {chord_max:.4f}]")
    print(f"    energy:             [{energy_min:.4f}, {energy_max:.4f}]")
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
            print(f"    {feat:<20} label={lbl:<10} → p{int(pct*100):02d} = {fmin + pct*(fmax-fmin):.4f}")
    print()

    query_tags = [t.lower() for t in merged.get("tags", [])]
    try:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        q_vec = _st_model.encode(" ".join(query_tags), normalize_embeddings=True)
        def tag_sim(tt):
            if not tt: return 0.0
            return _cosine_sim(q_vec, _st_model.encode(" ".join(tt), normalize_embeddings=True))
    except (ImportError, Exception):
        def tag_sim(tt):
            return _jaccard(query_tags, tt)

    records = []
    for _, row in df.iterrows():
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
        records.append({**row.to_dict(),
            "bpm_score": bpm_s, "danceability_score": dan_s,
            "chords_score": crd_s, "energy_score": eng_s,
            "tag_sim": tag_s, "composite_score": comp})

    scored = pd.DataFrame(records).sort_values("composite_score", ascending=False)
    print(f"  {'Title':<35} {'Orch':<25} bpm   dan   crd   eng   tag  → comp")
    print("  " + "─"*110)
    for _, r in scored.head(15).iterrows():
        print(
            f"  {str(r.get('title','')):<35} {str(r.get('orchestra','')):<25}"
            f" {r['bpm_score']:.2f}  {r['danceability_score']:.2f}  "
            f"{r['chords_score']:.2f}  {r['energy_score']:.2f}  "
            f"{r['tag_sim']:.2f}  → {r['composite_score']:.4f}"
        )
    print()
    return scored


# ── Step 6: tanda grouping and combo selection ─────────────────────────────

def step6_tanda(scored: pd.DataFrame, merged: dict) -> None:
    print(SEP)
    print("STEP 6 — Tanda grouping + best combination")
    print(SEP)

    style   = merged.get("style")
    n       = TANDA_SIZE.get(str(style).lower() if style else "", 4)
    print(f"  Style={style!r}  →  tanda size = {n}\n")

    if "combo_key" not in scored.columns:
        print("  ERROR: 'combo_key' column missing from DataFrame")
        return

    print(f"  combo_key groups with ≥{n} tracks:")
    best_mean, best_tanda, best_key = -1.0, [], ""

    for combo_key, group in scored.groupby("combo_key"):
        if len(group) < n:
            continue
        pool = group.head(20)
        print(f"    {combo_key!r}: {len(group)} tracks, top scores: "
              f"{list(pool['composite_score'].round(4).head(5))}")

        for idxs in itertools.combinations(range(len(pool)), n):
            rows = pool.iloc[list(idxs)]
            m = rows["composite_score"].mean()
            if m > best_mean:
                best_mean, best_tanda, best_key = m, rows.to_dict("records"), str(combo_key)

    print()
    if not best_tanda:
        print("  No valid tanda found — no combo_key group has enough tracks.\n")
        return

    print(f"  ★ Best tanda: {best_key}  mean_score={best_mean:.4f}")
    for i, t in enumerate(best_tanda, 1):
        print(
            f"    {i}. {t['title']:<35} | bpm={t.get('bpm_label'):<10} "
            f"dance={t.get('danceability_label'):<10} energy={t.get('energy_label'):<10} "
            f"score={t['composite_score']:.4f}"
        )
    print()


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/reduced_catalog.csv")
    parser.add_argument("--merged-json", default=None,
                        help="Path to a JSON file with a merged dict (skips LLM). "
                             "Defaults to the hardcoded FIXED_MERGED above.")
    args = parser.parse_args()

    if args.merged_json:
        import json
        merged = json.loads(Path(args.merged_json).read_text())
    else:
        merged = FIXED_MERGED

    print("\n" + SEP)
    print("AT-DJ select_tanda DEBUG")
    print(SEP)
    print("Merged bundle:")
    import json
    print(json.dumps(merged, indent=2))
    print()

    df = step0_load(args.csv)
    step1_inspect_vals(df, merged)
    hard   = step2_hard_filter(df, merged)
    pool   = step3_soft_filter(hard, merged)
    step4_tag_similarity(pool, merged)
    scored = step5_score(pool, merged, df)
    step6_tanda(scored, merged)


if __name__ == "__main__":
    main()
