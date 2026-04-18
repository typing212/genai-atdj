import pandas as pd
import random
from langchain_core.tools import tool
from atdj.config import CATALOG_PATH


def _load_catalog() -> pd.DataFrame:
    return pd.read_csv(CATALOG_PATH)


@tool
def search_catalog(
    style: str,
    decade: str,
    orchestra: str | None = None,
    exclude_track_ids: list[str] = [],
    limit: int = 20,
) -> list[dict]:
    """Search the catalog for tracks matching style and decade.
    Returns 3-4 tracks from the same combo (orchestra + singer + style)."""
    df = _load_catalog()

    # Filter by style and decade
    df = df[df["style"] == style]
    df = df[df["decade"] == decade]

    # Filter by orchestra if specified
    if orchestra:
        df = df[df["orchestra"].str.lower() == orchestra.lower()]

    # Exclude already used tracks
    if exclude_track_ids:
        df = df[~df["filename"].isin(exclude_track_ids)]

    if df.empty:
        return []

    # Group by combo_key and pick a valid combo (at least 3 tracks)
    valid_combos = [
        (key, group)
        for key, group in df.groupby("combo_key")
        if len(group) >= 3
    ]

    if not valid_combos:
        return []

    # Pick a random combo
    combo_key, combo_tracks = random.choice(valid_combos)

    # Take 3 or 4 tracks randomly
    n = random.choice([3, 4]) if len(combo_tracks) >= 4 else 3
    selected = combo_tracks.sample(n=n)

    return selected.to_dict(orient="records")


@tool
def validate_tanda(track_filenames: list[str]) -> dict:
    """Check if a list of track filenames forms a valid tanda."""
    df = _load_catalog()
    tracks = df[df["filename"].isin(track_filenames)]
    errors = []

    if len(tracks) < 3 or len(tracks) > 4:
        errors.append(f"Tanda must have 3-4 tracks, got {len(tracks)}")
    if tracks["orchestra"].nunique() > 1:
        errors.append(f"All tracks must share one orchestra: {tracks['orchestra'].unique().tolist()}")
    if tracks["style"].nunique() > 1:
        errors.append(f"All tracks must share one style: {tracks['style'].unique().tolist()}")
    if tracks["decade"].nunique() > 1:
        errors.append(f"All tracks must share one decade: {tracks['decade'].unique().tolist()}")

    return {"valid": len(errors) == 0, "errors": errors}


@tool
def get_energy_target(tanda_position: int, total_tandas: int) -> float:
    """Return the target energy level (0.0-1.0) for a given tanda position."""
    if total_tandas <= 0:
        return 0.5
    progress = tanda_position / total_tandas
    if progress < 0.4:
        return 0.3 + (progress / 0.4) * 0.4
    elif progress < 0.6:
        return 0.7 + ((progress - 0.4) / 0.2) * 0.2
    else:
        return 0.9 - ((progress - 0.6) / 0.4) * 0.4


@tool
def select_cortina(
    preceding_style: str,
    duration_seconds: float = 20.0,
) -> dict:
    """Select a cortina from the catalog to follow a tanda."""
    df = _load_catalog()
    cortinas = df[df["style"] == "cortina"]
    if cortinas.empty:
        return {
            "filename": "default_cortina",
            "file_path": "data/cortinas/default.mp3",
            "duration_seconds": duration_seconds
        }
    cortina = cortinas.sample(1).iloc[0]
    return cortina.to_dict()