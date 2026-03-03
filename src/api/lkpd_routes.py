from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from src.agent.jobs import MaterialJobStore
from src.agent.lkpd_storage import LkpdFileStorage
from src.agent.types import LkpdAsyncSubmitRequest
from src.auth import require_jwt
from src.config import settings
from src.core.api_response import ApiSuccessResponse
from src.core.exceptions import ServiceError
from src.api.job_submission import (
    build_job_accepted_response,
    enqueue_uploaded_job,
    validate_submit_request,
)
from src.api.schemas import JobAcceptedData


def build_lkpd_router(job_store: MaterialJobStore, lkpd_storage: LkpdFileStorage) -> APIRouter:
    router = APIRouter(tags=["lkpd"])
    lkpd_scopes = list(settings.jwt_required_scopes.get("/api/lkpd", ()))
    lkpd_file_scopes = list(
        settings.jwt_required_scopes.get("/api/lkpd/files/{file_id}", ())
    )

    @router.post(
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
        submit_request = validate_submit_request(
            LkpdAsyncSubmitRequest,
            user_id=user_id,
            callback_url=callback_url,
            activity_count=activity_count,
        )
        job_id = await enqueue_uploaded_job(
            job_store=job_store,
            job_kind="lkpd",
            submit_request=submit_request,
            file=file,
            failure_log_message="Failed to enqueue LKPD job",
            failure_public_message="Failed to enqueue LKPD job",
        )
        return build_job_accepted_response(
            request=http_request,
            job_id=job_id,
            message="LKPD queued for async processing.",
        )

    @router.get(
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

    return router
