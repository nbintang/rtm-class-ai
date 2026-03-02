from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from src.agent.types.common import MaterialInfo, SourceRef
from src.config import settings


class LkpdUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)
    activity_count: int = Field(default=settings.lkpd_default_activity_count)

    @model_validator(mode="after")
    def validate_activity_count_range(self) -> "LkpdUploadRequest":
        if self.activity_count < settings.lkpd_min_activity_count:
            raise ValueError(
                f"activity_count must be >= {settings.lkpd_min_activity_count}."
            )
        if self.activity_count > settings.lkpd_max_activity_count:
            raise ValueError(
                f"activity_count must be <= {settings.lkpd_max_activity_count}."
            )
        return self


class LkpdAsyncSubmitRequest(LkpdUploadRequest):
    callback_url: AnyHttpUrl

    def to_lkpd_upload_request(self) -> LkpdUploadRequest:
        return LkpdUploadRequest.model_validate(
            self.model_dump(exclude={"callback_url"})
        )


class LkpdActivity(BaseModel):
    activity_no: int = Field(ge=1)
    task: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    assessment_hint: str = Field(min_length=1)


class LkpdRubricItem(BaseModel):
    aspect: str = Field(min_length=1)
    criteria: str = Field(min_length=1)
    score_range: str = Field(min_length=1)


class LkpdContent(BaseModel):
    title: str = Field(min_length=1)
    learning_objectives: list[str] = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    activities: list[LkpdActivity] = Field(min_length=1)
    worksheet_template: str = Field(min_length=1)
    assessment_rubric: list[LkpdRubricItem] = Field(min_length=1)


class LkpdGeneratedPayload(BaseModel):
    lkpd: LkpdContent


class LkpdGenerateRuntimeResult(BaseModel):
    document_id: str
    material: MaterialInfo
    lkpd: LkpdContent
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LkpdGenerateResult(LkpdGenerateRuntimeResult):
    pdf_url: str = Field(min_length=1)
    pdf_expires_at: datetime


class LkpdSubmitAcceptedResponse(BaseModel):
    job_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"
    message: str = "LKPD queued for async processing."

