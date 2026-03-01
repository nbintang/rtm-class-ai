from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from src.config import settings


class SourceRef(BaseModel):
    chunk_id: str | None = None
    source_id: str | None = None
    excerpt: str


class ToolCallLog(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = None


GenerateType = Literal["mcq", "essay", "summary"]
JobKind = Literal["material", "lkpd"]
JobStatus = Literal[
    "accepted",
    "processing",
    "succeeded",
    "failed_processing",
    "failed_delivery",
]
CallbackStatus = Literal["succeeded", "failed_processing"]


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


class MaterialInfo(BaseModel):
    filename: str
    file_type: str
    extracted_chars: int


class McqQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[str]
    correct_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_options(self) -> "McqQuestion":
        if len(self.options) != 4:
            raise ValueError("MCQ options must contain exactly 4 items.")
        if len(set(self.options)) != len(self.options):
            raise ValueError("MCQ options must be unique.")
        if self.correct_answer not in self.options:
            raise ValueError("MCQ correct_answer must match one option.")
        return self


class McqQuiz(BaseModel):
    questions: list[McqQuestion]


class EssayQuestion(BaseModel):
    question: str = Field(min_length=1)
    expected_points: str = Field(min_length=1)


class EssayQuiz(BaseModel):
    questions: list[EssayQuestion]


class SummaryContent(BaseModel):
    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list)


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


class MaterialGeneratedPayload(BaseModel):
    mcq_quiz: McqQuiz | None = None
    essay_quiz: EssayQuiz | None = None
    summary: SummaryContent | None = None


class LkpdGeneratedPayload(BaseModel):
    lkpd: LkpdContent


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


class LkpdGenerateRuntimeResult(BaseModel):
    document_id: str
    material: MaterialInfo
    lkpd: LkpdContent
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LkpdGenerateResult(LkpdGenerateRuntimeResult):
    pdf_url: str = Field(min_length=1)
    pdf_expires_at: datetime


class MaterialSubmitAcceptedResponse(BaseModel):
    job_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"
    message: str = "Material queued for async processing."


class LkpdSubmitAcceptedResponse(BaseModel):
    job_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"
    message: str = "LKPD queued for async processing."


class CallbackErrorInfo(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MaterialWebhookResultPayload(BaseModel):
    event: Literal["material.generated"] = "material.generated"
    job_id: str = Field(min_length=1)
    status: CallbackStatus
    user_id: str = Field(min_length=1)
    result: MaterialGenerateResponse | None = None
    error: CallbackErrorInfo | None = None
    attempt: int = Field(ge=1)
    finished_at: datetime

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "MaterialWebhookResultPayload":
        if self.status == "succeeded":
            if self.result is None:
                raise ValueError("result is required when status is succeeded.")
            if self.error is not None:
                raise ValueError("error must be empty when status is succeeded.")
        if self.status == "failed_processing":
            if self.error is None:
                raise ValueError("error is required when status is failed_processing.")
            if self.result is not None:
                raise ValueError("result must be empty when status is failed_processing.")
        return self


class LkpdWebhookResultPayload(BaseModel):
    event: Literal["lkpd.generated"] = "lkpd.generated"
    job_id: str = Field(min_length=1)
    status: CallbackStatus
    user_id: str = Field(min_length=1)
    result: LkpdGenerateResult | None = None
    error: CallbackErrorInfo | None = None
    attempt: int = Field(ge=1)
    finished_at: datetime

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "LkpdWebhookResultPayload":
        if self.status == "succeeded":
            if self.result is None:
                raise ValueError("result is required when status is succeeded.")
            if self.error is not None:
                raise ValueError("error must be empty when status is succeeded.")
        if self.status == "failed_processing":
            if self.error is None:
                raise ValueError("error is required when status is failed_processing.")
            if self.result is not None:
                raise ValueError("result must be empty when status is failed_processing.")
        return self


class QueuedJob(BaseModel):
    job_id: str = Field(min_length=1)
    job_kind: JobKind
    status: JobStatus = "accepted"
    user_id: str = Field(min_length=1)
    callback_url: AnyHttpUrl
    request_payload: dict[str, Any] = Field(default_factory=dict)
    filename: str = Field(min_length=1)
    content_type: str | None = None
    file_b64: str = Field(min_length=1)
    callback_attempts: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None

    def parse_material_request(self) -> MaterialUploadRequest:
        return MaterialUploadRequest.model_validate(self.request_payload)

    def parse_lkpd_request(self) -> LkpdUploadRequest:
        return LkpdUploadRequest.model_validate(self.request_payload)
