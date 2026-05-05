from pydantic import BaseModel, Field
from typing import Optional, Union
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


class PlanSession(BaseModel):
    """One agent planning run. Lifecycle = a single PLAN chat request through the LangGraph.
    Not to be confused with the user-facing milonga session in the sidebar."""
    id: str
    name: str
