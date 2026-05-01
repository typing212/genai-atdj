"""Tests for PlaybackQueue."""

from atdj.playback.player import PlaybackQueue
from atdj.ui.page_main import _renumber_tanda_ids

ITEMS = [
    {"type": "song", "title": "Track A", "orchestra": "Orch A", "style": "TANGO", "duration": "3:00"},
    {"type": "cortina", "title": "Cortina 1", "duration": "0:20"},
    {"type": "song", "title": "Track B", "orchestra": "Orch B", "style": "VALS", "duration": "2:50"},
    {"type": "song", "title": "Track C", "orchestra": "Orch C", "style": "MILONGA", "duration": "2:40"},
]


def test_current_track_empty_queue():
    pq = PlaybackQueue()
    assert pq.current_track() is None


def test_current_track_returns_first():
    pq = PlaybackQueue(ITEMS)
    assert pq.current_track()["title"] == "Track A"


def test_next_track_advances():
    pq = PlaybackQueue(ITEMS)
    result = pq.next_track()
    assert result["title"] == "Cortina 1"
    assert pq.current_index == 1


def test_next_track_at_end_returns_none():
    pq = PlaybackQueue(ITEMS)
    pq._current_index = len(ITEMS) - 1
    result = pq.next_track()
    assert result is None
    assert pq.is_playing is False


def test_previous_track_at_start():
    pq = PlaybackQueue(ITEMS)
    result = pq.previous_track()
    assert result["title"] == "Track A"
    assert pq.current_index == 0


def test_previous_track_goes_back():
    pq = PlaybackQueue(ITEMS)
    pq._current_index = 2
    result = pq.previous_track()
    assert result["title"] == "Cortina 1"
    assert pq.current_index == 1


def test_skip_is_next():
    pq = PlaybackQueue(ITEMS)
    result = pq.skip()
    assert result["title"] == "Cortina 1"


def test_play_pause_toggle():
    pq = PlaybackQueue(ITEMS)
    assert pq.is_playing is False
    assert pq.play_pause() is True
    assert pq.is_playing is True
    assert pq.play_pause() is False
    assert pq.is_playing is False


def test_stop_resets():
    pq = PlaybackQueue(ITEMS)
    pq.play_pause()
    assert pq.is_playing is True
    pq.stop()
    assert pq.is_playing is False


def test_session_state_roundtrip():
    pq = PlaybackQueue(ITEMS)
    pq._current_index = 2
    pq._is_playing = True
    data = pq.to_session_state()
    pq2 = PlaybackQueue.from_session_state(data)
    assert pq2.current_index == 2
    assert pq2.is_playing is True
    assert len(pq2.items) == len(ITEMS)


def test_get_current_duration_from_string():
    pq = PlaybackQueue(ITEMS)
    assert pq.get_current_duration() == 180.0


def test_get_current_duration_from_seconds():
    pq = PlaybackQueue([{"type": "song", "title": "X", "duration_seconds": 192.5}])
    assert pq.get_current_duration() == 192.5


def test_move_up():
    pq = PlaybackQueue(ITEMS)
    assert pq.move_up(2)
    assert pq.items[1]["title"] == "Track B"
    assert pq.items[2]["title"] == "Cortina 1"


def test_move_up_at_zero():
    pq = PlaybackQueue(ITEMS)
    assert pq.move_up(0) is False


def test_move_down():
    pq = PlaybackQueue(ITEMS)
    assert pq.move_down(0)
    assert pq.items[0]["title"] == "Cortina 1"
    assert pq.items[1]["title"] == "Track A"


def test_remove_before_cursor():
    pq = PlaybackQueue(ITEMS)
    pq._current_index = 2
    pq.remove(0)
    assert pq.current_index == 1
    assert len(pq.items) == 3


def test_remove_at_cursor():
    pq = PlaybackQueue(ITEMS)
    pq._current_index = 1
    pq.remove(1)
    assert pq.current_index == 1
    assert pq.current_track()["title"] == "Track B"


# ── _renumber_tanda_ids — auto-heal stale tanda_id collisions ─────────────────

class TestRenumberTandaIds:
    """Locks in the 2026-05-01 fix for the 'next_tanda matched 12 tracks' bug.
    Stacked plans used to all start at tanda_id=0; this migration walks the
    playlist and assigns one id per cortina-bounded block."""

    def test_collision_across_stacked_plans_is_healed(self):
        # Three plans stacked, every one used tanda_id=0 (the pre-fix bug).
        items = [
            {"type": "song", "title": "P1-A", "tanda_id": 0},
            {"type": "song", "title": "P1-B", "tanda_id": 0},
            {"type": "cortina", "title": "C1"},
            {"type": "song", "title": "P2-A", "tanda_id": 0},
            {"type": "song", "title": "P2-B", "tanda_id": 0},
            {"type": "cortina", "title": "C2"},
            {"type": "song", "title": "P3-A", "tanda_id": 0},
        ]
        changed = _renumber_tanda_ids(items)
        assert changed is True
        assert [it.get("tanda_id") for it in items if it.get("type") == "song"] == [0, 0, 1, 1, 2]

    def test_already_correct_is_noop(self):
        items = [
            {"type": "song", "title": "A", "tanda_id": 0},
            {"type": "cortina", "title": "C1"},
            {"type": "song", "title": "B", "tanda_id": 1},
        ]
        changed = _renumber_tanda_ids(items)
        assert changed is False

    def test_cortinas_dont_get_tanda_id(self):
        items = [
            {"type": "song", "title": "A", "tanda_id": 0},
            {"type": "cortina", "title": "C1"},  # no tanda_id field — should stay that way
            {"type": "song", "title": "B", "tanda_id": 0},
        ]
        _renumber_tanda_ids(items)
        assert "tanda_id" not in items[1]

    def test_consecutive_cortinas_dont_advance(self):
        # Two cortinas back-to-back shouldn't bump the id twice.
        items = [
            {"type": "song", "title": "A", "tanda_id": 0},
            {"type": "cortina", "title": "C1"},
            {"type": "cortina", "title": "C2"},
            {"type": "song", "title": "B", "tanda_id": 9},
        ]
        _renumber_tanda_ids(items)
        assert [it.get("tanda_id") for it in items if it.get("type") == "song"] == [0, 1]

    def test_empty_playlist(self):
        items = []
        assert _renumber_tanda_ids(items) is False
        assert items == []
