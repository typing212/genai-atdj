from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class FeedbackEvent(BaseModel):
    id: str
    session_id: str
    timestamp: datetime
    event_type: Literal[
        "energy_up", "energy_down", "skip_tanda",
        "repeat_orchestra", "avoid_orchestra",
        "floor_full", "floor_empty",
        "qa_query", "manual_override",
    ]
    payload: dict = Field(default_factory=dict)
    processed: bool = False
    agent_response: Optional[str] = None
