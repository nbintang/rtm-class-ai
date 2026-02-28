from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.core.constants import DEFAULT_COLLECTION


class RagDocumentInput(BaseModel):
    id: str | None = None
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIndexRequest(BaseModel):
    collection_name: str = DEFAULT_COLLECTION
    text: str | None = None
    documents: list[RagDocumentInput] | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "RagIndexRequest":
        has_text = bool(self.text and self.text.strip())
        has_docs = bool(self.documents)
        if not has_text and not has_docs:
            raise ValueError("Provide either 'text' or 'documents'.")
        return self


class RagIndexResponse(BaseModel):
    collection_name: str
    indexed_chunks: int
    document_count: int
    chunk_ids: list[str]
