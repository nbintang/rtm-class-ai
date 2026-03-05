from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.agent.jobs import MaterialJobStore
from src.agent.lkpd_pdf import render_lkpd_pdf
from src.agent.lkpd_storage import LkpdFileStorage
from src.agent.runtime import (
    AgentRuntime,
    LkpdValidationError,
    MaterialTooLargeError,
    MaterialValidationError,
)
from src.agent.types import (
    CallbackErrorInfo,
    LkpdGenerateResult,
    LkpdWebhookResultPayload,
    MaterialWebhookResultPayload,
    QueuedJob,
)
from src.config import settings

logger = logging.getLogger(__name__)


async def process_material_job(
    *,
    runtime: AgentRuntime,
    job_store: MaterialJobStore,
    job: QueuedJob,
) -> MaterialWebhookResultPayload:
    await job_store.update_job(job.job_id, status="processing")
    finished_at = datetime.now(UTC)

    try:
        request = job.parse_material_request()
        result = await runtime.invoke_material_upload(
            request=request,
            file_bytes=job_store.decode_file_bytes(job),
            filename=job.filename,
            content_type=job.content_type,
            job_id=job.job_id,
            material_id=job.material_id,
            requested_by_id=job.requested_by_id,
        )
        callback_payload = MaterialWebhookResultPayload(
            job_id=job.job_id,
            status="succeeded",
            user_id=job.user_id,
            result=result,
            attempt=1,
            finished_at=finished_at,
        )
        await job_store.update_job(
            job.job_id,
            status="succeeded",
            clear_last_error=True,
        )
        return callback_payload
    except Exception as exc:
        logger.exception("Material processing failed for job %s", job.job_id)
        callback_payload = MaterialWebhookResultPayload(
            job_id=job.job_id,
            status="failed_processing",
            user_id=job.user_id,
            error=CallbackErrorInfo(
                code=map_error_code(exc),
                message=str(exc),
            ),
            attempt=1,
            finished_at=finished_at,
        )
        await job_store.update_job(
            job.job_id,
            status="failed_processing",
            last_error=str(exc),
        )
        return callback_payload


async def process_lkpd_job(
    *,
    runtime: AgentRuntime,
    job_store: MaterialJobStore,
    lkpd_storage: LkpdFileStorage,
    job: QueuedJob,
) -> LkpdWebhookResultPayload:
    await job_store.update_job(job.job_id, status="processing")
    finished_at = datetime.now(UTC)

    try:
        request = job.parse_lkpd_request()
        runtime_result = await runtime.invoke_lkpd_upload(
            request=request,
            file_bytes=job_store.decode_file_bytes(job),
            filename=job.filename,
            content_type=job.content_type,
        )
        pdf_bytes = render_lkpd_pdf(
            lkpd=runtime_result.lkpd,
            material=runtime_result.material,
            document_id=runtime_result.document_id,
        )
        stored_file = lkpd_storage.save_pdf(pdf_bytes)
        base_url = settings.app_public_base_url.rstrip("/")
        pdf_url = f"{base_url}/api/lkpd/files/{stored_file.file_id}"
        callback_result = LkpdGenerateResult(
            document_id=runtime_result.document_id,
            material=runtime_result.material,
            lkpd=runtime_result.lkpd,
            pdf_url=pdf_url,
            pdf_expires_at=stored_file.expires_at,
            sources=runtime_result.sources,
            warnings=runtime_result.warnings,
        )

        callback_payload = LkpdWebhookResultPayload(
            job_id=job.job_id,
            status="succeeded",
            user_id=job.user_id,
            result=callback_result,
            attempt=1,
            finished_at=finished_at,
        )
        await job_store.update_job(
            job.job_id,
            status="succeeded",
            clear_last_error=True,
        )
        return callback_payload
    except Exception as exc:
        logger.exception("LKPD processing failed for job %s", job.job_id)
        callback_payload = LkpdWebhookResultPayload(
            job_id=job.job_id,
            status="failed_processing",
            user_id=job.user_id,
            error=CallbackErrorInfo(
                code=map_error_code(exc),
                message=str(exc),
            ),
            attempt=1,
            finished_at=finished_at,
        )
        await job_store.update_job(
            job.job_id,
            status="failed_processing",
            last_error=str(exc),
        )
        return callback_payload


def map_error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if "tool_use_failed" in message:
        return "model_tool_use_failed"
    if isinstance(exc, MaterialTooLargeError):
        return "material_too_large"
    if isinstance(exc, MaterialValidationError):
        return "material_validation_error"
    if isinstance(exc, LkpdValidationError):
        return "lkpd_validation_error"
    return "processing_error"

