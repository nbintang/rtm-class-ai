from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from src.agent.types.aliases import CallbackStatus, JobKind, JobStatus
from src.agent.types.lkpd import LkpdGenerateResult, LkpdUploadRequest
from src.agent.types.material import MaterialGenerateResponse, MaterialUploadRequest


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
    material_id: str | None = None
    requested_by_id: str | None = None
    callback_url: AnyHttpUrl | None = None
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

