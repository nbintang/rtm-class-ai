from pydantic import BaseModel, Field


class SummaryContent(BaseModel):
    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list)

