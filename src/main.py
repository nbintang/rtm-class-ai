from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import Response

from src.agent.callback import WebhookCallbackClient
from src.agent.jobs import MaterialJobStore
from src.agent.lkpd_storage import LkpdFileStorage
from src.agent.runtime import AgentRuntime
from src.agent.types import (
    GenerateType,
    LkpdAsyncSubmitRequest,
    MaterialAsyncSubmitRequest,
)
from src.agent.worker import MaterialJobWorker
from src.auth import require_jwt
from src.config import settings
from src.core.api_response import (
    ApiSuccessResponse,
    attach_meta_to_json_response,
    build_request_id,
    build_success_payload,
)
from src.core.constants import APP_NAME, APP_VERSION
from src.core.exceptions import ServiceError, register_exception_handlers
from src.core.logging import configure_logging


configure_logging()
logger = logging.getLogger(__name__)

agent_runtime = AgentRuntime()
job_store = MaterialJobStore()
callback_client = WebhookCallbackClient()
lkpd_storage = LkpdFileStorage()
job_worker = MaterialJobWorker(
    runtime=agent_runtime,
    job_store=job_store,
    callback_client=callback_client,
    lkpd_storage=lkpd_storage,
)


class JobAcceptedData(BaseModel):
    job_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    await agent_runtime.initialize()
    await job_store.initialize()
    await callback_client.initialize()
    await lkpd_storage.initialize()
    job_worker.start()
    try:
        yield
    finally:
        await job_worker.stop()
        await callback_client.shutdown()
        await job_store.shutdown()
        await agent_runtime.shutdown()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=app_lifespan)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = build_request_id()
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api"):
        return attach_meta_to_json_response(response, request_id)
    return response


register_exception_handlers(app)

material_scopes = list(settings.jwt_required_scopes.get("/api/material", ()))
lkpd_scopes = list(settings.jwt_required_scopes.get("/api/lkpd", ()))
lkpd_file_scopes = list(
    settings.jwt_required_scopes.get("/api/lkpd/files/{file_id}", ())
)


@app.post(
    "/api/material",
    response_model=ApiSuccessResponse[JobAcceptedData],
    response_model_exclude_none=True,
    status_code=202,
    dependencies=[Depends(require_jwt(material_scopes))],
)
async def webhook_material(
    http_request: Request,
    user_id: str = Form(...),
    file: UploadFile = File(...),
    callback_url: str = Form(...),
    generate_types: list[GenerateType] = Form(...),
    mcq_count: int = Form(default=settings.default_mcq_count),
    essay_count: int = Form(default=settings.default_essay_count),
    summary_max_words: int = Form(default=settings.default_summary_max_words),
    mcp_enabled: bool = Form(default=True),
) -> ApiSuccessResponse[JobAcceptedData]:
    try:
        submit_request = MaterialAsyncSubmitRequest(
            user_id=user_id,
            callback_url=callback_url,
            generate_types=generate_types,
            mcq_count=mcq_count,
            essay_count=essay_count,
            summary_max_words=summary_max_words,
            mcp_enabled=mcp_enabled,
        )
    except ValidationError as exc:
        raise ServiceError(
            "Request validation failed.",
            status_code=422,
            details=exc.errors(),
        ) from exc

    file_bytes = await file.read()
    max_bytes = settings.material_max_file_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ServiceError(
            f"File exceeds maximum size of {settings.material_max_file_mb} MB.",
            status_code=413,
        )

    filename = file.filename or "uploaded_material"

    try:
        job_id = await job_store.enqueue_job(
            job_kind="material",
            request=submit_request,
            file_bytes=file_bytes,
            filename=filename,
            content_type=file.content_type,
        )
        return build_success_payload(
            request=http_request,
            data=JobAcceptedData(job_id=job_id),
            message="Material queued for async processing.",
        )
    except Exception as exc:
        logger.exception("Failed to enqueue material job")
        raise ServiceError(f"Failed to enqueue material job: {exc}", status_code=503) from exc


@app.post(
    "/api/lkpd",
    response_model=ApiSuccessResponse[JobAcceptedData],
    response_model_exclude_none=True,
    status_code=202,
    dependencies=[Depends(require_jwt(lkpd_scopes))],
)
async def webhook_lkpd(
    http_request: Request,
    user_id: str = Form(...),
    file: UploadFile = File(...),
    callback_url: str = Form(...),
    activity_count: int = Form(default=settings.lkpd_default_activity_count),
) -> ApiSuccessResponse[JobAcceptedData]:
    try:
        submit_request = LkpdAsyncSubmitRequest(
            user_id=user_id,
            callback_url=callback_url,
            activity_count=activity_count,
        )
    except ValidationError as exc:
        raise ServiceError(
            "Request validation failed.",
            status_code=422,
            details=exc.errors(),
        ) from exc

    file_bytes = await file.read()
    max_bytes = settings.material_max_file_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ServiceError(
            f"File exceeds maximum size of {settings.material_max_file_mb} MB.",
            status_code=413,
        )

    filename = file.filename or "uploaded_material"
    try:
        job_id = await job_store.enqueue_job(
            job_kind="lkpd",
            request=submit_request,
            file_bytes=file_bytes,
            filename=filename,
            content_type=file.content_type,
        )
        return build_success_payload(
            request=http_request,
            data=JobAcceptedData(job_id=job_id),
            message="LKPD queued for async processing.",
        )
    except Exception as exc:
        logger.exception("Failed to enqueue LKPD job")
        raise ServiceError(f"Failed to enqueue LKPD job: {exc}", status_code=503) from exc


@app.get(
    "/api/lkpd/files/{file_id}",
    dependencies=[Depends(require_jwt(lkpd_file_scopes))],
)
async def get_lkpd_file(file_id: str) -> FileResponse:
    path = lkpd_storage.get_pdf_path(file_id)
    if path is None:
        raise ServiceError("LKPD file not found or expired.", status_code=404)
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"{file_id}.pdf",
    )
