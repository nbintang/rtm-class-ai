from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from src.agent.jobs import MaterialJobStore
from src.agent.types import GenerateType, MaterialAsyncSubmitRequest
from src.auth import require_jwt
from src.config import settings
from src.core.api_response import ApiSuccessResponse
from src.api.job_submission import (
    build_job_accepted_response,
    enqueue_uploaded_job,
    validate_submit_request,
)
from src.api.schemas import JobAcceptedData


GENERATION_MESSAGE: dict[GenerateType, str] = {
    "mcq": "MCQ queued for async processing.",
    "essay": "Essay queued for async processing.",
    "summary": "Summary queued for async processing.",
}


def _build_submit_request(
    *,
    user_id: str,
    job_id: str,
    material_id: str,
    requested_by_id: str,
    callback_url: str | None,
    generate_types: list[GenerateType],
    mcq_count: int,
    essay_count: int,
    summary_max_words: int,
    mcp_enabled: bool,
) -> MaterialAsyncSubmitRequest:
    return validate_submit_request(
        MaterialAsyncSubmitRequest,
        user_id=user_id,
        job_id=job_id,
        material_id=material_id,
        requested_by_id=requested_by_id,
        callback_url=callback_url,
        generate_types=generate_types,
        mcq_count=mcq_count,
        essay_count=essay_count,
        summary_max_words=summary_max_words,
        mcp_enabled=mcp_enabled,
    )


async def _enqueue_from_submit_request(
    *,
    job_store: MaterialJobStore,
    request: Request,
    submit_request: MaterialAsyncSubmitRequest,
    file: UploadFile,
    message: str,
) -> ApiSuccessResponse[JobAcceptedData]:
    job_id = await enqueue_uploaded_job(
        job_store=job_store,
        job_kind="material",
        submit_request=submit_request,
        file=file,
        failure_log_message="Failed to enqueue material job",
        failure_public_message="Failed to enqueue material job",
    )
    return build_job_accepted_response(
        request=request,
        job_id=job_id,
        message=message,
    )


async def enqueue_material_job(
    *,
    job_store: MaterialJobStore,
    request: Request,
    user_id: str,
    job_id: str,
    material_id: str,
    requested_by_id: str,
    file: UploadFile,
    callback_url: str | None,
    generate_type: Literal["mcq", "essay", "summary"],
    mcq_count: int | None,
    essay_count: int | None,
    summary_max_words: int | None,
    mcp_enabled: bool,
) -> ApiSuccessResponse[JobAcceptedData]:
    submit_request = _build_submit_request(
        user_id=user_id,
        job_id=job_id,
        material_id=material_id,
        requested_by_id=requested_by_id,
        callback_url=callback_url,
        generate_types=[generate_type],
        mcq_count=settings.default_mcq_count if mcq_count is None else mcq_count,
        essay_count=settings.default_essay_count if essay_count is None else essay_count,
        summary_max_words=(
            settings.default_summary_max_words
            if summary_max_words is None
            else summary_max_words
        ),
        mcp_enabled=mcp_enabled,
    )
    return await _enqueue_from_submit_request(
        job_store=job_store,
        request=request,
        submit_request=submit_request,
        message=GENERATION_MESSAGE[generate_type],
        file=file,
    )


def build_material_router(job_store: MaterialJobStore) -> APIRouter:
    router = APIRouter(tags=["material"])
    material_scopes = list(settings.jwt_required_scopes.get("/api/material", ()))
    mcq_scopes = list(settings.jwt_required_scopes.get("/api/mcq", material_scopes))
    essay_scopes = list(settings.jwt_required_scopes.get("/api/essay", material_scopes))
    summary_scopes = list(settings.jwt_required_scopes.get("/api/summary", material_scopes))

    @router.post(
        "/api/material",
        response_model=ApiSuccessResponse[JobAcceptedData],
        response_model_exclude_none=True,
        status_code=202,
        dependencies=[Depends(require_jwt(material_scopes))],
    )
    async def webhook_material(
        http_request: Request,
        user_id: str = Form(...),
        job_id: str = Form(...),
        material_id: str = Form(...),
        requested_by_id: str = Form(...),
        file: UploadFile = File(...),
        callback_url: str | None = Form(default=None),
        generate_types: list[GenerateType] = Form(...),
        mcq_count: int = Form(default=settings.default_mcq_count),
        essay_count: int = Form(default=settings.default_essay_count),
        summary_max_words: int = Form(default=settings.default_summary_max_words),
        mcp_enabled: bool = Form(default=True),
    ) -> ApiSuccessResponse[JobAcceptedData]:
        submit_request = _build_submit_request(
            user_id=user_id,
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            callback_url=callback_url,
            generate_types=generate_types,
            mcq_count=mcq_count,
            essay_count=essay_count,
            summary_max_words=summary_max_words,
            mcp_enabled=mcp_enabled,
        )
        return await _enqueue_from_submit_request(
            job_store=job_store,
            request=http_request,
            submit_request=submit_request,
            file=file,
            message="Material queued for async processing.",
        )

    @router.post(
        "/api/mcq",
        response_model=ApiSuccessResponse[JobAcceptedData],
        response_model_exclude_none=True,
        status_code=202,
        dependencies=[Depends(require_jwt(mcq_scopes))],
    )
    async def webhook_mcq(
        http_request: Request,
        user_id: str = Form(...),
        job_id: str = Form(...),
        material_id: str = Form(...),
        requested_by_id: str = Form(...),
        file: UploadFile = File(...),
        callback_url: str | None = Form(default=None),
        mcq_count: int = Form(default=settings.default_mcq_count),
        mcp_enabled: bool = Form(default=True),
    ) -> ApiSuccessResponse[JobAcceptedData]:
        return await enqueue_material_job(
            job_store=job_store,
            request=http_request,
            user_id=user_id,
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            file=file,
            callback_url=callback_url,
            generate_type="mcq",
            mcq_count=mcq_count,
            essay_count=None,
            summary_max_words=None,
            mcp_enabled=mcp_enabled,
        )

    @router.post(
        "/api/essay",
        response_model=ApiSuccessResponse[JobAcceptedData],
        response_model_exclude_none=True,
        status_code=202,
        dependencies=[Depends(require_jwt(essay_scopes))],
    )
    async def webhook_essay(
        http_request: Request,
        user_id: str = Form(...),
        job_id: str = Form(...),
        material_id: str = Form(...),
        requested_by_id: str = Form(...),
        file: UploadFile = File(...),
        callback_url: str | None = Form(default=None),
        essay_count: int = Form(default=settings.default_essay_count),
        mcp_enabled: bool = Form(default=True),
    ) -> ApiSuccessResponse[JobAcceptedData]:
        return await enqueue_material_job(
            job_store=job_store,
            request=http_request,
            user_id=user_id,
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            file=file,
            callback_url=callback_url,
            generate_type="essay",
            mcq_count=None,
            essay_count=essay_count,
            summary_max_words=None,
            mcp_enabled=mcp_enabled,
        )

    @router.post(
        "/api/summary",
        response_model=ApiSuccessResponse[JobAcceptedData],
        response_model_exclude_none=True,
        status_code=202,
        dependencies=[Depends(require_jwt(summary_scopes))],
    )
    async def webhook_summary(
        http_request: Request,
        user_id: str = Form(...),
        job_id: str = Form(...),
        material_id: str = Form(...),
        requested_by_id: str = Form(...),
        file: UploadFile = File(...),
        callback_url: str | None = Form(default=None),
        summary_max_words: int = Form(default=settings.default_summary_max_words),
        mcp_enabled: bool = Form(default=True),
    ) -> ApiSuccessResponse[JobAcceptedData]:
        return await enqueue_material_job(
            job_store=job_store,
            request=http_request,
            user_id=user_id,
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            file=file,
            callback_url=callback_url,
            generate_type="summary",
            mcq_count=None,
            essay_count=None,
            summary_max_words=summary_max_words,
            mcp_enabled=mcp_enabled,
        )

    return router
