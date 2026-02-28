from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class SourceRef(BaseModel):
    chunk_id: str | None = None
    source_id: str | None = None
    excerpt: str
