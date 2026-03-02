from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    chunk_id: str | None = None
    source_id: str | None = None
    excerpt: str


class ToolCallLog(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = None


class MaterialInfo(BaseModel):
    filename: str
    file_type: str
    extracted_chars: int

