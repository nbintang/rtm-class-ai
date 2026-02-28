from datetime import datetime

from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    owner_id: str | None = None


class MaterialRead(BaseModel):
    id: str
    title: str
    owner_id: str | None = None
    text_preview: str
    source_type: str
    created_at: datetime


class MaterialDetail(MaterialRead):
    extracted_text: str

