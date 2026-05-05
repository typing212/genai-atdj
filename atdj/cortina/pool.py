"""
atdj/cortina/pool.py
--------------------
Fallback cortina selector using a pre-built pool of pop/non-tango songs.

When Lyria is unavailable (no Gemini API key), this module picks the best
matching cortina from data/cortinas/pool/ based on BPM and energy similarity
to the preceding tanda.

Public API
----------
build_pool_features()          -> extracts BPM + energy for all songs in pool, saves CSV
find_best_cortina(tanda_summary, exclude) -> returns a playlist item dict
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from atdj.config import ROOT_DIR

POOL_DIR      = ROOT_DIR / "data" / "cortinas" / "pool"
FEATURES_CSV  = ROOT_DIR / "data" / "cortinas" / "pool_features.csv"


# ── Feature extraction ────────────────────────────────────────────────────────

def build_pool_features(force: bool = False) -> pd.DataFrame:
    """Extract BPM and energy for every mp3 in the pool and save to CSV.

    Skips extraction if CSV already exists unless force=True.
    """
    if FEATURES_CSV.exists() and not force:
        return pd.read_csv(FEATURES_CSV)

    import librosa
    import numpy as np

    files = sorted(POOL_DIR.glob("*.mp3")) + sorted(POOL_DIR.glob("*.wav"))
    if not files:
        raise FileNotFoundError(f"No audio files found in {POOL_DIR}")

    rows = []
    for f in files:
        try:
            y, sr = librosa.load(str(f), sr=None, mono=True, duration=60)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = float(np.atleast_1d(tempo)[0])
            energy = float(np.mean(librosa.feature.rms(y=y)))
            # Normalise energy to 0-1 range (typical rms is 0.01-0.3)
            energy_norm = min(energy / 0.3, 1.0)
            rows.append({"filename": f.name, "file_path": str(f), "bpm": round(bpm, 1), "energy": round(energy_norm, 3)})
            print(f"  ✓ {f.name}  BPM={bpm:.0f}  energy={energy_norm:.2f}")
        except Exception as e:
            print(f"  ✗ {f.name}: {e}")

    df = pd.DataFrame(rows)
    FEATURES_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FEATURES_CSV, index=False)
    print(f"\nSaved {len(df)} tracks to {FEATURES_CSV}")
    return df


# ── Matching ──────────────────────────────────────────────────────────────────

def find_best_cortina(
    tanda_summary: dict,
    exclude: list[str] | None = None,
) -> dict:
    """Pick the pool song that best matches tanda BPM and energy.

    Parameters
    ----------
    tanda_summary : output of _summarize_tanda — needs 'avg_bpm' and 'energy_label'
    exclude       : list of filenames already used (avoid repeats)

    Returns a playlist item dict ready to append to the queue.
    """
    if not FEATURES_CSV.exists():
        build_pool_features()

    df = pd.read_csv(FEATURES_CSV)
    if df.empty:
        return _placeholder()

    exclude = exclude or []
    df = df[~df["filename"].isin(exclude)]
    if df.empty:
        df = pd.read_csv(FEATURES_CSV)  # reset if all excluded

    # Target values from tanda
    target_bpm = tanda_summary.get("avg_bpm") or 120
    energy_label = tanda_summary.get("energy_label", "moderate")
    target_energy = {"low": 0.2, "moderate": 0.5, "high": 0.8}.get(energy_label, 0.5)

    # Score: weighted distance (BPM matters more)
    df = df.copy()
    df["score"] = (
        0.7 * abs(df["bpm"] - target_bpm) / 60 +
        0.3 * abs(df["energy"] - target_energy)
    )

    # Pick from top 3 randomly to add variety
    top = df.nsmallest(3, "score")
    chosen = top.sample(1).iloc[0]

    duration_secs = 30
    return {
        "type": "cortina",
        "title": Path(chosen["filename"]).stem,
        "file_path": chosen["file_path"],
        "duration": f"0:{duration_secs:02d}",
        "source": "pool",
    }


def _placeholder() -> dict:
    return {"type": "cortina", "title": "Cortina", "duration": "0:20", "source": "agent"}
