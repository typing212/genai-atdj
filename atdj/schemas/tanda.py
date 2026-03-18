from pydantic import BaseModel, Field, model_validator
from typing import Optional
from atdj.schemas.track import Track, TangoStyle


class Tanda(BaseModel):
    id: str
    tracks: list[Track] = Field(min_length=3, max_length=4)
    style: TangoStyle
    orchestra: str
    era_decade: int
    total_duration_seconds: float = 0.0
    energy_level: float = Field(ge=0.0, le=1.0)
    position_in_session: Optional[int] = None
    generated_by: str = "agent"
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def validate_homogeneity(self) -> "Tanda":
        styles = {t.style for t in self.tracks}
        if len(styles) > 1:
            raise ValueError(f"All tracks must share one style: {styles}")
        self.total_duration_seconds = sum(t.duration_seconds for t in self.tracks)
        return self
