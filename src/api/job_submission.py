from __future__ import annotations

import logging
from typing import TypeVar

from fastapi import Request, UploadFile
from pydantic import BaseModel, ValidationError

from src.agent.jobs import MaterialJobStore
from src.agent.types import JobKind
from src.config import settings
from src.core.api_response import ApiSuccessResponse, build_success_payload
from src.core.exceptions import ServiceError

from src.api.schemas import JobAcceptedData

logger = logging.getLogger(__name__)

TSubmitModel = TypeVar("TSubmitModel", bound=BaseModel)


def validate_submit_request(model_type: type[TSubmitModel], **kwargs: object) -> TSubmitModel:
    try:
        return model_type(**kwargs)
    except ValidationError as exc:
        raise ServiceError(
            "Request validation failed.",
            status_code=422,
            details=exc.errors(),
        ) from exc


async def read_and_validate_upload(file: UploadFile) -> tuple[bytes, str]:
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise ServiceError(
            "Request validation failed.",
            status_code=422,
            details=[
                {
                    "type": "value_error",
                    "loc": ["body", "file"],
                    "msg": "Uploaded file must not be empty.",
                    "input": "",
                }
            ],
        )

    max_bytes = settings.material_max_file_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ServiceError(
            f"File exceeds maximum size of {settings.material_max_file_mb} MB.",
            status_code=413,
        )
    return file_bytes, (file.filename or "uploaded_material")


async def enqueue_uploaded_job(
    *,
    job_store: MaterialJobStore,
    job_kind: JobKind,
    submit_request: BaseModel,
    file: UploadFile,
    failure_log_message: str,
    failure_public_message: str,
) -> str:
    file_bytes, filename = await read_and_validate_upload(file)
    try:
        return await job_store.enqueue_job(
            job_kind=job_kind,
            request=submit_request,
            file_bytes=file_bytes,
            filename=filename,
            content_type=file.content_type,
        )
    except Exception as exc:
        logger.exception(failure_log_message)
        raise ServiceError(f"{failure_public_message}: {exc}", status_code=503) from exc


def build_job_accepted_response(
    *,
    request: Request,
    job_id: str,
    message: str,
) -> ApiSuccessResponse[JobAcceptedData]:
    return build_success_payload(
        request=request,
        data=JobAcceptedData(job_id=job_id),
        message=message,
    )
