"""Filename resolution sweep — every catalog row must resolve to an existing audio file.

Runs `PlaybackQueue.resolve_file_path` against every row in the feature catalog
(`data/essentia_newsamp.csv`) and reports any that return None or point at a
missing file. Cortina resolution is also exercised.

Pure-IO test — no LLM, no Streamlit, no audio decoding.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from atdj.config import CATALOG_PATH, CORTINAS_DIR
from atdj.playback.player import PlaybackQueue


def _load_catalog_rows() -> list[dict]:
    df = pd.read_csv(CATALOG_PATH)
    rows: list[dict] = []
    for _, r in df.iterrows():
        rows.append(
            {
                "type": "song",
                "title": r["title"],
                "orchestra": r.get("orchestra", "") or "",
                "filename": r.get("filename", ""),
            }
        )
    return rows


CATALOG_ROWS = _load_catalog_rows()


@pytest.mark.parametrize("row", CATALOG_ROWS, ids=lambda r: f"{r['title']} | {r['orchestra']}")
def test_song_resolves_to_existing_file(row):
    """Every (title, orchestra) pair from the catalog must resolve to a file on disk."""
    pq = PlaybackQueue()
    item = {"type": "song", "title": row["title"], "orchestra": row["orchestra"]}
    path = pq.resolve_file_path(item)
    assert path is not None, (
        f"resolve_file_path returned None for title={row['title']!r} "
        f"orchestra={row['orchestra']!r} (catalog filename={row['filename']!r})"
    )
    assert Path(path).exists(), f"Resolved path does not exist on disk: {path}"


def test_resolution_summary():
    """Aggregate report — fails with a list of every unresolved row."""
    pq = PlaybackQueue()
    failures: list[str] = []
    for row in CATALOG_ROWS:
        item = {"type": "song", "title": row["title"], "orchestra": row["orchestra"]}
        path = pq.resolve_file_path(item)
        if path is None:
            failures.append(f"  - UNRESOLVED  title={row['title']!r}  orch={row['orchestra']!r}  csv-filename={row['filename']!r}")
        elif not Path(path).exists():
            failures.append(f"  - MISSING ON DISK  resolved={path!r}  for title={row['title']!r}")
    if failures:
        msg = f"{len(failures)} of {len(CATALOG_ROWS)} catalog rows failed resolution:\n" + "\n".join(failures)
        pytest.fail(msg)


def test_cortina_resolves_when_directory_present():
    """Cortina resolution should return a real file when the cortinas dir has any audio."""
    cortinas_path = Path(CORTINAS_DIR)
    if not cortinas_path.exists():
        pytest.skip(f"No cortinas directory at {cortinas_path}")
    files = list(cortinas_path.glob("*.mp3")) + list(cortinas_path.glob("*.wav"))
    if not files:
        pytest.skip(f"Cortinas directory {cortinas_path} is empty")
    pq = PlaybackQueue()
    item = {"type": "cortina", "title": files[0].stem}
    path = pq.resolve_file_path(item)
    assert path is not None, "Cortina with title matching an existing file must resolve"
    assert Path(path).exists(), f"Cortina resolved to missing file: {path}"
