from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from src.agent.types.aliases import GenerateType
from src.agent.types.common import MaterialInfo, SourceRef, ToolCallLog
from src.agent.types.quiz import EssayQuiz, McqQuiz
from src.agent.types.summary import SummaryContent


class MaterialUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)
    generate_types: list[GenerateType] = Field(min_length=1)
    mcq_count: int = Field(default=10, ge=1, le=20)
    essay_count: int = Field(default=3, ge=1, le=10)
    summary_max_words: int = Field(default=200, ge=80, le=400)
    mcp_enabled: bool = True

    @model_validator(mode="after")
    def validate_generate_types_unique(self) -> "MaterialUploadRequest":
        if len(set(self.generate_types)) != len(self.generate_types):
            raise ValueError("generate_types must not contain duplicates.")
        return self


class MaterialAsyncSubmitRequest(MaterialUploadRequest):
    callback_url: AnyHttpUrl

    def to_material_upload_request(self) -> MaterialUploadRequest:
        return MaterialUploadRequest.model_validate(
            self.model_dump(exclude={"callback_url"})
        )


class MaterialGeneratedPayload(BaseModel):
    mcq_quiz: McqQuiz | None = None
    essay_quiz: EssayQuiz | None = None
    summary: SummaryContent | None = None


class MaterialGenerateResponse(BaseModel):
    user_id: str
    document_id: str
    material: MaterialInfo
    mcq_quiz: McqQuiz | None = None
    essay_quiz: EssayQuiz | None = None
    summary: SummaryContent | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MaterialSubmitAcceptedResponse(BaseModel):
    job_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"
    message: str = "Material queued for async processing."

