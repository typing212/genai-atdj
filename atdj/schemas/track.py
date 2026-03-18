from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class TangoStyle(str, Enum):
    TANGO   = "tango"
    VALS    = "vals"
    MILONGA = "milonga"
    CORTINA = "cortina"


class AudioQuality(str, Enum):
    RAW      = "raw"
    ENHANCED = "enhanced"


class Track(BaseModel):
    id: str
    title: str
    orchestra: str
    singer: Optional[str] = None
    style: TangoStyle
    year: int
    decade: int
    duration_seconds: float = Field(gt=0)
    file_path: str
    audio_quality: AudioQuality = AudioQuality.RAW
    enhanced_file_path: Optional[str] = None

    # Audio features — populated by atdj/audio/features.py
    bpm: Optional[float] = None
    key: Optional[str] = None
    energy: Optional[float] = None
    danceability: Optional[float] = None
    brightness: Optional[float] = None
    snr_estimate_db: Optional[float] = None
    embedding_id: Optional[str] = None

    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    model_config = {"use_enum_values": True}

    @field_validator("decade", mode="before")
    @classmethod
    def derive_decade(cls, v, info):
        if v is None and "year" in info.data:
            return info.data["year"] // 10 * 10
        return v
