import pytest
from atdj.schemas.track import Track, TangoStyle, AudioQuality
from atdj.schemas.tanda import Tanda
from atdj.schemas.session import MilongaSession
from atdj.schemas.feedback import FeedbackEvent
from datetime import datetime


# --- Track ---

def make_track(**overrides):
    base = dict(
        id="test_001",
        title="El Retirado",
        orchestra="Di Sarli",
        style=TangoStyle.TANGO,
        year=1942,
        decade=1940,
        duration_seconds=180.0,
        file_path="data/raw/test_001.mp3",
    )
    base.update(overrides)
    return Track(**base)


def test_valid_track():
    t = make_track()
    assert t.id == "test_001"
    assert t.style == "tango"
    assert t.audio_quality == "raw"



def test_track_negative_duration():
    with pytest.raises(Exception):
        make_track(duration_seconds=-1.0)


def test_track_optional_features_default_none():
    t = make_track()
    assert t.bpm is None
    assert t.energy is None
    assert t.key is None


# --- Tanda ---

def make_tanda_tracks(n=3, **track_overrides):
    return [make_track(id=f"t_{i}", **track_overrides) for i in range(n)]


def test_valid_tanda():
    tracks = make_tanda_tracks(3)
    tanda = Tanda(
        id="tanda_001",
        tracks=tracks,
        style=TangoStyle.TANGO,
        orchestra="Di Sarli",
        era_decade=1940,
        energy_level=0.6,
    )
    assert tanda.total_duration_seconds == 180.0 * 3


def test_tanda_too_few_tracks():
    with pytest.raises(Exception):
        Tanda(
            id="tanda_002",
            tracks=make_tanda_tracks(2),
            style=TangoStyle.TANGO,
            orchestra="Di Sarli",
            era_decade=1940,
            energy_level=0.5,
        )


def test_tanda_too_many_tracks():
    with pytest.raises(Exception):
        Tanda(
            id="tanda_003",
            tracks=make_tanda_tracks(5),
            style=TangoStyle.TANGO,
            orchestra="Di Sarli",
            era_decade=1940,
            energy_level=0.5,
        )


def test_tanda_mixed_orchestras_allowed():
    # Orchestra homogeneity is a soft rule enforced by the planner (WP-05), not Pydantic
    tracks = make_tanda_tracks(3)
    tracks[2] = make_track(id="t_other", orchestra="Troilo")
    tanda = Tanda(
        id="tanda_004",
        tracks=tracks,
        style=TangoStyle.TANGO,
        orchestra="Di Sarli",
        era_decade=1940,
        energy_level=0.5,
    )
    assert tanda.id == "tanda_004"


def test_tanda_mixed_styles():
    tracks = make_tanda_tracks(3)
    tracks[2] = make_track(id="t_other", style=TangoStyle.VALS)
    with pytest.raises(ValueError, match="style"):
        Tanda(
            id="tanda_005",
            tracks=tracks,
            style=TangoStyle.TANGO,
            orchestra="Di Sarli",
            era_decade=1940,
            energy_level=0.5,
        )


def test_tanda_energy_out_of_range():
    with pytest.raises(Exception):
        Tanda(
            id="tanda_006",
            tracks=make_tanda_tracks(3),
            style=TangoStyle.TANGO,
            orchestra="Di Sarli",
            era_decade=1940,
            energy_level=1.5,
        )


# --- MilongaSession ---

def make_session(**overrides):
    base = dict(
        id="sess_001",
        name="Test Milonga",
        started_at=datetime.now(),
    )
    base.update(overrides)
    return MilongaSession(**base)


def test_session_planning_mode_default():
    s = make_session()
    assert s.planning_mode == "convention"


def test_session_planning_mode_flexible():
    s = make_session(planning_mode="flexible")
    assert s.planning_mode == "flexible"


def test_session_planning_mode_invalid():
    with pytest.raises(Exception):
        make_session(planning_mode="strict")


# --- FeedbackEvent ---

def test_valid_feedback_event():
    event = FeedbackEvent(
        id="evt_001",
        session_id="sess_001",
        timestamp=datetime.now(),
        event_type="energy_up",
    )
    assert event.processed is False


def test_invalid_feedback_event_type():
    with pytest.raises(Exception):
        FeedbackEvent(
            id="evt_002",
            session_id="sess_001",
            timestamp=datetime.now(),
            event_type="invalid_type",
        )
