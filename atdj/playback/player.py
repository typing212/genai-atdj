"""PlaybackQueue — manages a flat playlist with a cursor and playback state."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from atdj.config import CATALOG_PATH, RAW_DIR, CORTINAS_DIR, PROCESSED_DIR


class PlaybackQueue:

    def __init__(self, items: list[dict] | None = None):
        self._items: list[dict] = list(items) if items else []
        self._current_index: int = 0
        self._is_playing: bool = False
        self._catalog_df: pd.DataFrame | None = None

    @property
    def items(self) -> list[dict]:
        return self._items

    @items.setter
    def items(self, value: list[dict]) -> None:
        self._items = value

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def current_track(self) -> dict | None:
        if not self._items or self._current_index >= len(self._items):
            return None
        return self._items[self._current_index]

    def next_track(self) -> dict | None:
        if not self._items:
            return None
        if self._current_index < len(self._items) - 1:
            self._current_index += 1
            return self.current_track()
        self._is_playing = False
        return None

    def previous_track(self) -> dict | None:
        if not self._items:
            return None
        if self._current_index > 0:
            self._current_index -= 1
        return self.current_track()

    def skip(self) -> dict | None:
        return self.next_track()

    def jump_to(self, index: int) -> dict | None:
        """Jump the cursor directly to any index in the playlist."""
        if not self._items or index < 0 or index >= len(self._items):
            return None
        self._current_index = index
        self._is_playing = True
        return self.current_track()

    def stop(self) -> None:
        self._is_playing = False

    def clear(self) -> None:
        """Empty the playlist and reset the cursor / playing flag.

        Called by the 'Clear' button in the Full Playlist section
        (`page_main.py:1525`). Was previously missing — clicking Clear raised
        AttributeError and crashed the page.
        """
        self._items = []
        self._current_index = 0
        self._is_playing = False

    def play_pause(self) -> bool:
        self._is_playing = not self._is_playing
        return self._is_playing

    def _load_catalog(self) -> pd.DataFrame:
        if self._catalog_df is None:
            self._catalog_df = pd.read_csv(CATALOG_PATH)
        return self._catalog_df

    def resolve_file_path(self, item: dict) -> str | None:
        if item.get("type") == "cortina":
            return self._resolve_cortina(item)
        return self._resolve_song(item)

    def _resolve_song(self, item: dict) -> str | None:
        df = self._load_catalog()
        title = item.get("title", "")
        mask = df["title"].str.lower() == title.lower()
        orch = item.get("orchestra", "")
        if orch:
            mask = mask & (df["orchestra"].str.lower() == orch.lower())
        matches = df[mask]
        if matches.empty:
            return None
        filename = matches.iloc[0]["filename"]
        processed = PROCESSED_DIR / (Path(filename).stem + "_enhanced.wav")
        if processed.exists():
            return str(processed)
        raw = RAW_DIR / filename
        if raw.exists():
            return str(raw)
        return None

    def resolve_raw_path(self, item: dict) -> str | None:
        """Always return the raw source path, ignoring any processed version."""
        if item.get("type") == "cortina":
            return None
        df = self._load_catalog()
        title = item.get("title", "")
        mask = df["title"].str.lower() == title.lower()
        orch = item.get("orchestra", "")
        if orch:
            mask = mask & (df["orchestra"].str.lower() == orch.lower())
        matches = df[mask]
        if matches.empty:
            return None
        filename = matches.iloc[0]["filename"]
        path = RAW_DIR / filename
        return str(path) if path.exists() else None

    def _resolve_cortina(self, item: dict) -> str | None:
        # 1. Honour an explicit file_path stored by pool.py / generator.py.
        stored = item.get("file_path")
        if stored and Path(stored).exists():
            return stored

        # 2. Fuzzy title-match across CORTINAS_DIR and all subdirectories
        #    (covers pool/, generated/, and top-level cortina files).
        cortinas_path = Path(CORTINAS_DIR)
        if not cortinas_path.exists():
            return None
        files = (
            list(cortinas_path.glob("*.mp3")) + list(cortinas_path.glob("*.wav")) +
            list(cortinas_path.glob("**/*.mp3")) + list(cortinas_path.glob("**/*.wav"))
        )
        seen: set[str] = set()
        files = [f for f in files if not (str(f) in seen or seen.add(str(f)))]
        if not files:
            return None
        title_lower = item.get("title", "").lower()
        for f in files:
            if f.stem.lower() in title_lower or title_lower in f.stem.lower():
                return str(f)
        return str(files[0])

    def get_current_duration(self) -> float | None:
        item = self.current_track()
        if item is None:
            return None
        dur = item.get("duration_seconds")
        if dur is not None:
            return float(dur)
        dur_str = item.get("duration", "")
        if ":" in dur_str:
            parts = dur_str.split(":")
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                return None
        if item.get("type") == "cortina":
            return 20.0
        df = self._load_catalog()
        title = item.get("title", "")
        mask = df["title"].str.lower() == title.lower()
        matches = df[mask]
        if not matches.empty and "duration_seconds" in matches.columns:
            return float(matches.iloc[0]["duration_seconds"])
        return None

    def move_up(self, index: int) -> bool:
        if index <= 0 or index >= len(self._items):
            return False
        self._items[index], self._items[index - 1] = self._items[index - 1], self._items[index]
        if self._current_index == index:
            self._current_index = index - 1
        elif self._current_index == index - 1:
            self._current_index = index
        return True

    def move_down(self, index: int) -> bool:
        if index < 0 or index >= len(self._items) - 1:
            return False
        self._items[index], self._items[index + 1] = self._items[index + 1], self._items[index]
        if self._current_index == index:
            self._current_index = index + 1
        elif self._current_index == index + 1:
            self._current_index = index
        return True

    def remove(self, index: int) -> bool:
        if index < 0 or index >= len(self._items):
            return False
        self._items.pop(index)
        if index < self._current_index:
            self._current_index -= 1
        elif index == self._current_index:
            if self._current_index >= len(self._items):
                self._current_index = max(0, len(self._items) - 1)
        return True

    def to_session_state(self) -> dict:
        return {
            "items": self._items,
            "current_index": self._current_index,
            "is_playing": self._is_playing,
        }

    @classmethod
    def from_session_state(cls, data: dict) -> PlaybackQueue:
        pq = cls(data.get("items", []))
        pq._current_index = data.get("current_index", 0)
        pq._is_playing = data.get("is_playing", False)
        return pq
