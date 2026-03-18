from pydantic import BaseModel, Field
from typing import Optional, Union, Literal
from datetime import datetime
from atdj.schemas.tanda import Tanda


class Cortina(BaseModel):
    id: str
    file_path: str
    duration_seconds: float = Field(ge=10.0, le=35.0)
    source: str
    preceding_tanda_id: Optional[str] = None
    features: dict[str, float] = Field(default_factory=dict)


class QueueItem(BaseModel):
    item_type: str
    content: Union[Tanda, Cortina]
    scheduled_position: int
    played: bool = False
    played_at: Optional[datetime] = None


class MilongaSession(BaseModel):
    id: str
    name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    target_duration_minutes: int = Field(default=180, ge=60, le=300)
    queue: list[QueueItem] = Field(default_factory=list)
    current_position: int = 0
    energy_arc: list[float] = Field(default_factory=list)
    actual_energies: list[float] = Field(default_factory=list)
    available_track_ids: list[str] = Field(default_factory=list)
    styles_ratio: dict[str, float] = Field(
        default_factory=lambda: {"tango": 0.70, "vals": 0.20, "milonga": 0.10}
    )
    preferred_orchestras: list[str] = Field(default_factory=list)
    avoid_repeat_orchestra_within: int = 3
    planning_mode: Literal["convention", "flexible"] = "convention"
