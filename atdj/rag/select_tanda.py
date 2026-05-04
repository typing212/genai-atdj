"""
atdj/rag/select_tanda.py
------------------------
Candidate filtering and tanda selection from a TranslationBundle.

Pipeline
--------
1. Hard-filter the catalog by non-null scalar fields from the prompt bundle
   (style, decade, year, orchestra, singer, album, bpm_label, danceability_label,
   chords_changes_rate, energy_label, key).  Null / None values are skipped.

2. Score every passing track with a linear combination of five components:
     • bpm_score         – how close the track's BPM label is to the target
     • danceability_score
     • chords_score
     • energy_score
     • tag_similarity    – semantic cosine similarity between track tags and
                           prompt tags (via sentence-transformers)
   Label fields (low/moderate/high/slow/…) are mapped to an ordinal numeric value
   and the "distance" to the target label becomes the score so that the direction
   of "better" is always the same for every feature.

3. Group passing tracks by combo_key (orchestra | singer | style).
   A valid tanda requires tracks from the same combo_key.
   Tanda size: 4 for tango, 3 for vals / milonga (matches prompt style if
   present, otherwise uses the track style for each group).

4. For each combo_key that has enough tracks, enumerate all valid tanda
   combinations and pick the one with the highest mean composite score.

5. Return the best tanda (list of track dicts with scores) plus the full
   candidate DataFrame for inspection.

Usage
-----
python -m atdj.rag.select_tanda \
  --csv data/reduced_catalog.csv \
  --prompt "romantic vals from the 1940s, not too fast, smooth but still danceable"

Or import and call directly:

    from atdj.rag.select_tanda import select_tanda
    from atdj.rag.prompt_to_features import TwoLayerPromptTranslator, load_catalog

    df = load_catalog("data/reduced_catalog.csv")
    translator = TwoLayerPromptTranslator(df)
    bundle = translator.translate(prompt_text)
    result = select_tanda(bundle, df)
    print(result)
"""

from __future__ import annotations

import ast
import itertools
import json
import warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

# sentence-transformers is used only for tag similarity.
# If it is not installed we fall back to a lightweight token-overlap score.
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ST_AVAILABLE = False
    warnings.warn(
        "[select_tanda] sentence-transformers not installed. "
        "Falling back to token-overlap for tag similarity. "
        "Install with: pip install sentence-transformers",
        stacklevel=2,
    )

# ── Constants ──────────────────────────────────────────────────────────────

# Label → percentile target for numeric scoring.
# When the LLM says "high", we want the track's raw value to be near the p75
# of the catalog distribution for that feature; "low" → near p25, etc.
# The scoring function computes this target from the full catalog at runtime.
LABEL_PERCENTILE = {
    "slow":      0.25,
    "low":       0.25,
    "moderate":  0.50,
    "fast":      0.75,
    "high":      0.75,
    "very fast": 0.90,
}

# Feature weights for the composite score (must sum to 1.0).
WEIGHTS = {
    "bpm": 0.20,
    "danceability": 0.20,
    "chords": 0.15,
    "energy": 0.20,
    "tags": 0.25,
}

# Tanda sizes by style.
TANDA_SIZE: dict[str, int] = {
    "tango": 4,
    "vals": 3,
    "milonga": 3,
}
DEFAULT_TANDA_SIZE = 4

# Embedding model (all-MiniLM-L6-v2 is small and fast, no API key needed).
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


# ── Embedding model — two-level cache ─────────────────────────────────────
#
# Level 1 (Streamlit session): st.cache_resource — one load per server process.
# Level 2 (CLI / tests): module-level singleton — one load per Python process.
#
# _st_is_running() gates which path is taken so show_spinner (which requires
# a live session context) is never called from bare-Python / test contexts.

_model: Optional["SentenceTransformer"] = None


def _st_is_running() -> bool:
    """True only when executing inside a live Streamlit session."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _load_model_plain() -> Optional["SentenceTransformer"]:
    global _model
    if not _ST_AVAILABLE:
        return None
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _get_model() -> Optional["SentenceTransformer"]:
    if _st_is_running():
        import streamlit as st

        @st.cache_resource
        def _cached_model():
            if not _ST_AVAILABLE:
                return None
            return SentenceTransformer(EMBEDDING_MODEL_NAME)

        return _cached_model()
    return _load_model_plain()


# ── Catalog feature ranges — module-level cache ────────────────────────────
#
# The four (min, max) pairs are derived from the full catalog and never change
# mid-session. Cached after the first call; invalidated if the catalog changes
# (detected via a fingerprint of the bpm column values).

_catalog_ranges: Optional[dict] = None
_catalog_ranges_key: Optional[tuple] = None


def _get_catalog_ranges(catalog_df: pd.DataFrame) -> dict:
    """Return {feature: (min, max)} for the four scored features, cached."""
    global _catalog_ranges, _catalog_ranges_key

    key = tuple(catalog_df["bpm"].dropna().values)
    if _catalog_ranges is not None and key == _catalog_ranges_key:
        return _catalog_ranges

    def _range(col: str):
        vals = catalog_df[col].dropna().astype(float)
        return float(vals.min()), float(vals.max())

    _catalog_ranges = {
        "bpm":                 _range("bpm"),
        "danceability":        _range("danceability"),
        "chords_changes_rate": _range("chords_changes_rate"),
        "energy":              _range("energy"),
    }
    _catalog_ranges_key = key
    return _catalog_ranges


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_tags(raw) -> list[str]:
    """Parse a tags value that may be a stringified list, a plain string, or already a list."""
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


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _tag_similarity_embedding(query_tags: list[str], track_tags: list[str]) -> float:
    """
    Semantic similarity via sentence-transformers.
    Embeds the joined tag strings and returns cosine similarity.
    """
    model = _get_model()
    if model is None or not query_tags or not track_tags:
        return 0.0
    q_text = " ".join(query_tags)
    t_text = " ".join(track_tags)
    vecs = model.encode([q_text, t_text], normalize_embeddings=True)
    return float(np.dot(vecs[0], vecs[1]))  # already normalized → cosine


def _tag_similarity_overlap(query_tags: list[str], track_tags: list[str]) -> float:
    """
    Fallback token-overlap Jaccard similarity when sentence-transformers
    is not installed.
    """
    if not query_tags or not track_tags:
        return 0.0
    q_set = set(query_tags)
    t_set = set(track_tags)
    intersection = q_set & t_set
    union = q_set | t_set
    return len(intersection) / len(union) if union else 0.0


def _tag_similarity(query_tags: list[str], track_tags: list[str]) -> float:
    if _ST_AVAILABLE:
        return _tag_similarity_embedding(query_tags, track_tags)
    return _tag_similarity_overlap(query_tags, track_tags)


def _numeric_score(target_label: Optional[str], track_value: float,
                   feat_min: float, feat_max: float) -> float:
    """
    Score a track's raw numeric feature value against a label-derived target.

    Steps
    -----
    1. Convert target_label → a target numeric value using LABEL_PERCENTILE and
       the feature's observed [feat_min, feat_max] range from the full catalog.
       e.g. label="high"  → target = feat_min + 0.75 * (feat_max - feat_min)
            label="low"   → target = feat_min + 0.25 * (feat_max - feat_min)
            label="moderate" → target = feat_min + 0.50 * (feat_max - feat_min)

    2. score = 1 − |track_value − target| / feature_range

    This means:
    - A track whose raw value exactly matches the target gets score = 1.0
    - Direction is correct: "high" maps to a high numeric target, "slow" to low
    - All four features are scored on the same [0, 1] scale regardless of units
    - Missing label or degenerate range → neutral score 0.5
    """
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


# ── Data class for results ─────────────────────────────────────────────────

@dataclass
class TandaResult:
    tanda: list[dict[str, Any]]          # selected tracks with scores
    combo_key: str
    mean_score: float
    candidates: list[dict[str, Any]]     # all tracks that passed hard filters
    query_bundle: dict[str, Any]         # the merged feature dict used


# ── Core logic ─────────────────────────────────────────────────────────────

def _str_eq(df: pd.DataFrame, col: str, value) -> "pd.Series":
    """Return a boolean mask: rows where df[col] == value (case-insensitive)."""
    val = str(value).strip().lower()
    return df[col].astype(str).str.strip().str.lower() == val


def _hard_filter(df: pd.DataFrame, merged: dict) -> pd.DataFrame:
    """
    Hard filter: year, decade, orchestra, singer, style, album.
    Null values are skipped (not constrained).
    Year is only applied when decade is absent.
    """
    mask = pd.Series([True] * len(df), index=df.index)

    for field, col in [
        ("style",     "style"),
        ("decade",    "decade"),
        ("orchestra", "orchestra"),
        ("singer",    "singer"),
        ("album",     "album"),
    ]:
        val = merged.get(field)
        if val is not None:
            mask &= _str_eq(df, col, val)

    year_val = merged.get("year")
    if year_val is not None and merged.get("decade") is None:
        try:
            mask &= df["year"].fillna(-1).astype(int) == int(year_val)
        except Exception:
            pass

    return df[mask].copy()


def _soft_filter(df: pd.DataFrame, merged: dict) -> pd.DataFrame:
    """
    Soft (semi-hard) filter: bpm_label, danceability_label, key,
    chords_changes_rate, energy_label.
    Only non-null values from merged are applied.
    chords uses the chords_changes_rate_label column in the catalog.
    """
    mask = pd.Series([True] * len(df), index=df.index)

    for field, col in [
        ("bpm_label",          "bpm_label"),
        ("danceability_label", "danceability_label"),
        ("key",                "key"),
        ("energy_label",       "energy_label"),
    ]:
        val = merged.get(field)
        if val is not None:
            mask &= _str_eq(df, col, val)

    ccr = merged.get("chords_changes_rate")
    if ccr is not None:
        col = "chords_changes_rate_label" if "chords_changes_rate_label" in df.columns else "chords_changes_rate"
        mask &= _str_eq(df, col, ccr)

    return df[mask].copy()


def _score_candidates(df: pd.DataFrame, merged: dict,
                      catalog_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a composite_score column to the filtered DataFrame.

    Uses raw numeric feature values (bpm, danceability, chords_changes_rate,
    energy) rather than labels for scoring.  The target_label from merged is
    converted to a numeric target via the full catalog's feature distribution
    (percentile-based), so "high" always means a high raw value and "slow"
    always means a low raw value.

    Components (each in [0, 1]):
      bpm_score         – numeric proximity of track bpm to target
      danceability_score
      chords_score      – uses chords_changes_rate column (raw float)
      energy_score
      tag_sim           – cosine similarity of tag embeddings (Jaccard fallback)
    """
    # Pre-compute feature ranges from the FULL catalog so targets are
    # calibrated to the global distribution, not just the filtered subset.
    # Result is module-level cached — free after the first call.
    ranges = _get_catalog_ranges(catalog_df)
    bpm_min,    bpm_max    = ranges["bpm"]
    dance_min,  dance_max  = ranges["danceability"]
    chord_min,  chord_max  = ranges["chords_changes_rate"]
    energy_min, energy_max = ranges["energy"]

    query_tags = [str(t).lower() for t in merged.get("tags", []) if t]

    bpm_scores, dance_scores, chord_scores, energy_scores, tag_scores = [], [], [], [], []

    for _, row in df.iterrows():
        bpm_scores.append(_numeric_score(
            merged.get("bpm_label"),
            float(row.get("bpm") or 0),
            bpm_min, bpm_max,
        ))
        dance_scores.append(_numeric_score(
            merged.get("danceability_label"),
            float(row.get("danceability") or 0),
            dance_min, dance_max,
        ))
        chord_scores.append(_numeric_score(
            merged.get("chords_changes_rate"),
            float(row.get("chords_changes_rate") or 0),   # raw float column
            chord_min, chord_max,
        ))
        energy_scores.append(_numeric_score(
            merged.get("energy_label"),
            float(row.get("energy") or 0),
            energy_min, energy_max,
        ))
        track_tags = _parse_tags(row.get("tags", ""))
        tag_scores.append(_tag_similarity(query_tags, track_tags))

    df = df.copy()
    df["bpm_score"]          = bpm_scores
    df["danceability_score"] = dance_scores
    df["chords_score"]       = chord_scores
    df["energy_score"]       = energy_scores
    df["tag_sim"]            = tag_scores

    df["composite_score"] = (
        WEIGHTS["bpm"]          * df["bpm_score"]
        + WEIGHTS["danceability"] * df["danceability_score"]
        + WEIGHTS["chords"]       * df["chords_score"]
        + WEIGHTS["energy"]       * df["energy_score"]
        + WEIGHTS["tags"]         * df["tag_sim"]
    )

    return df.sort_values("composite_score", ascending=False)


def _tanda_size_for(style: Optional[str]) -> int:
    if style is None:
        return DEFAULT_TANDA_SIZE
    return TANDA_SIZE.get(str(style).strip().lower(), DEFAULT_TANDA_SIZE)


def _best_tanda_for_group(group_df: pd.DataFrame, n: int) -> tuple[list[dict], float]:
    """
    From the top candidates in a combo_key group, find the combination of `n`
    tracks that maximises mean composite_score.

    We limit the search pool to the top-20 tracks to keep combinations tractable.
    """
    pool = group_df.head(20)
    if len(pool) < n:
        return [], -1.0

    best_combo: list[dict] = []
    best_mean = -1.0

    for combo_indices in itertools.combinations(range(len(pool)), n):
        rows = pool.iloc[list(combo_indices)]
        mean_score = rows["composite_score"].mean()
        if mean_score > best_mean:
            best_mean = mean_score
            best_combo = rows.to_dict(orient="records")

    return best_combo, best_mean


def select_tanda(
    bundle,
    catalog_df: pd.DataFrame,
) -> TandaResult:
    """
    Main entry point.

    Parameters
    ----------
    bundle : TranslationBundle
        Output from TwoLayerPromptTranslator.translate()
    catalog_df : pd.DataFrame
        Full catalog DataFrame (from load_catalog or pd.read_csv).

    Returns
    -------
    TandaResult
        .tanda         → list of track dicts (with score columns) for the best tanda
        .combo_key     → the combo_key of the chosen group
        .mean_score    → mean composite score of the best tanda
        .candidates    → all tracks that passed hard filters (scored)
        .query_bundle  → the merged dict used for filtering/scoring
    """
    merged: dict = bundle.merged if hasattr(bundle, "merged") else bundle

    if "combo_key" not in catalog_df.columns:
        raise ValueError("catalog_df must contain a 'combo_key' column.")

    prompt_style = merged.get("style")
    n = _tanda_size_for(prompt_style)

    # ── Step 1: hard filter (always applied) ─────────────────────────────
    hard = _hard_filter(catalog_df, merged)
    if hard.empty:
        print("[select_tanda] No tracks passed the hard filter. Returning empty tanda.")
        return TandaResult(tanda=[], combo_key="", mean_score=0.0,
                           candidates=[], query_bundle=merged)

    # ── Step 2: try soft filter on top of hard filter ────────────────────
    # Determine required tanda size per group (use prompt style if given,
    # otherwise infer from each group's style).
    def _min_tracks_needed(df: pd.DataFrame) -> int:
        """Minimum tracks needed across any combo_key group to form a tanda."""
        if prompt_style:
            return n
        # Check if any group has enough tracks for its style's tanda size
        for ck, grp in df.groupby("combo_key"):
            gs = grp["style"].iloc[0] if "style" in grp.columns else None
            if len(grp) >= _tanda_size_for(gs):
                return 0   # at least one valid group exists
        return 999  # no group has enough

    soft = _soft_filter(hard, merged)

    # Count how many combo_key groups have enough tracks after soft filter
    def _enough_groups(df: pd.DataFrame) -> bool:
        for ck, grp in df.groupby("combo_key"):
            gs = grp["style"].iloc[0] if "style" in grp.columns else None
            needed = n if prompt_style else _tanda_size_for(gs)
            if len(grp) >= needed:
                return True
        return False

    if _enough_groups(soft):
        print(f"[select_tanda] Using soft-filtered pool ({len(soft)} tracks).")
        pool = soft
        used_soft = True
    else:
        print(f"[select_tanda] Soft filter left no viable groups "
              f"({len(soft)} tracks). Falling back to hard-filter pool ({len(hard)} tracks).")
        pool = hard
        used_soft = False

    # ── Step 3: score ─────────────────────────────────────────────────────
    scored = _score_candidates(pool, merged, catalog_df)

    # ── Step 4: best tanda per combo_key ─────────────────────────────────
    best_tanda: list[dict] = []
    best_combo_key = ""
    best_mean = -1.0

    for combo_key, group in scored.groupby("combo_key"):
        group_n = n if prompt_style else _tanda_size_for(
            group["style"].iloc[0] if "style" in group.columns else None
        )
        tanda_tracks, mean_score = _best_tanda_for_group(group, group_n)
        if mean_score > best_mean:
            best_mean = mean_score
            best_tanda = tanda_tracks
            best_combo_key = str(combo_key)

    return TandaResult(
        tanda=best_tanda,
        combo_key=best_combo_key,
        mean_score=best_mean,
        candidates=scored.to_dict(orient="records"),
        query_bundle=merged,
    )


# ── CLI ────────────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Select a tanda from a natural-language prompt.")
    parser.add_argument("--csv", default="data/reduced_catalog.csv", help="Path to reduced_catalog.csv")
    parser.add_argument("--prompt", required=True, help="Natural-language DJ prompt")
    parser.add_argument("--provider", default="openai", choices=["openai", "claude", "gemini"],
                        help="LLM provider (overrides LLM_PROVIDER env var)")
    parser.add_argument("--top-candidates", type=int, default=10,
                        help="Number of top candidates to print alongside the chosen tanda")
    args = parser.parse_args()

    from atdj.rag.prompt_to_features import build_translator, load_catalog

    df = load_catalog(args.csv)
    translator = build_translator(df, provider=args.provider)
    bundle = translator.translate(args.prompt)

    print("\n── Prompt translation ──")
    print(json.dumps(bundle.merged, ensure_ascii=False, indent=2))

    result = select_tanda(bundle, df)

    print(f"\n── Best tanda  (combo_key: {result.combo_key}, mean_score: {result.mean_score:.4f}) ──")
    if not result.tanda:
        print("  No valid tanda found.")
    else:
        for i, track in enumerate(result.tanda, 1):
            print(
                f"  {i}. {track.get('title')} | {track.get('orchestra')} | "
                f"{track.get('singer')} | {track.get('decade')} | "
                f"composite={track.get('composite_score', 0):.4f}"
            )

    print(f"\n── Top {args.top_candidates} candidates (before tanda grouping) ──")
    for i, row in enumerate(result.candidates[: args.top_candidates], 1):
        print(
            f"  {i:>2}. {row.get('title'):<35} | {row.get('orchestra'):<25} | "
            f"bpm_s={row.get('bpm_score', 0):.2f} "
            f"dance_s={row.get('danceability_score', 0):.2f} "
            f"chord_s={row.get('chords_score', 0):.2f} "
            f"energy_s={row.get('energy_score', 0):.2f} "
            f"tag_s={row.get('tag_sim', 0):.2f} "
            f"→ {row.get('composite_score', 0):.4f}"
        )


if __name__ == "__main__":
    _cli_main()
