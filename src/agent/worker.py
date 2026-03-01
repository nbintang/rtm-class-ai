from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime
from typing import Any

from src.agent.callback import WebhookCallbackClient
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


class MaterialJobWorker:
    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        job_store: MaterialJobStore,
        callback_client: WebhookCallbackClient,
        lkpd_storage: LkpdFileStorage,
    ) -> None:
        self._runtime = runtime
        self._job_store = job_store
        self._callback_client = callback_client
        self._lkpd_storage = lkpd_storage
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._last_cleanup_at = datetime.now(UTC)

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._run_periodic_cleanup()
            try:
                job = await self._job_store.pop_next_job(timeout_seconds=1)
            except Exception:
                logger.exception("Failed to pop job from queue.")
                await asyncio.sleep(1)
                continue

            if job is None:
                continue

            try:
                await self._process_job(job)
            except Exception:
                logger.exception("Unexpected worker failure while processing job %s", job.job_id)

    def _run_periodic_cleanup(self) -> None:
        now = datetime.now(UTC)
        if (now - self._last_cleanup_at).total_seconds() < 60:
            return
        self._last_cleanup_at = now
        try:
            removed = self._lkpd_storage.cleanup_expired_files()
            if removed:
                logger.info("Cleaned up %s expired LKPD PDF file(s).", removed)
        except Exception:
            logger.exception("Failed to cleanup expired LKPD files.")

    async def _process_job(self, job: QueuedJob) -> None:
        if job.job_kind == "material":
            await self._process_material_job(job)
            return
        if job.job_kind == "lkpd":
            await self._process_lkpd_job(job)
            return
        logger.error("Unsupported job kind '%s' for job %s", job.job_kind, job.job_id)

    async def _process_material_job(self, job: QueuedJob) -> None:
        await self._job_store.update_job(job.job_id, status="processing")

        finished_at = datetime.now(UTC)
        try:
            request = job.parse_material_request()
            result = await self._runtime.invoke_material_upload(
                request=request,
                file_bytes=self._job_store.decode_file_bytes(job),
                filename=job.filename,
                content_type=job.content_type,
            )
            callback_payload = MaterialWebhookResultPayload(
                job_id=job.job_id,
                status="succeeded",
                user_id=job.user_id,
                result=result,
                attempt=1,
                finished_at=finished_at,
            )
            await self._job_store.update_job(
                job.job_id,
                status="succeeded",
                clear_last_error=True,
            )
        except Exception as exc:
            callback_payload = MaterialWebhookResultPayload(
                job_id=job.job_id,
                status="failed_processing",
                user_id=job.user_id,
                error=CallbackErrorInfo(
                    code=self._map_error_code(exc),
                    message=str(exc),
                ),
                attempt=1,
                finished_at=finished_at,
            )
            await self._job_store.update_job(
                job.job_id,
                status="failed_processing",
                last_error=str(exc),
            )

        delivered = await self._deliver_with_retry(job=job, payload=callback_payload)
        if not delivered:
            await self._job_store.update_job(
                job.job_id,
                status="failed_delivery",
                last_error="Callback delivery failed after max retries.",
            )

    async def _process_lkpd_job(self, job: QueuedJob) -> None:
        await self._job_store.update_job(job.job_id, status="processing")

        finished_at = datetime.now(UTC)
        try:
            request = job.parse_lkpd_request()
            runtime_result = await self._runtime.invoke_lkpd_upload(
                request=request,
                file_bytes=self._job_store.decode_file_bytes(job),
                filename=job.filename,
                content_type=job.content_type,
            )
            pdf_bytes = render_lkpd_pdf(
                lkpd=runtime_result.lkpd,
                material=runtime_result.material,
                document_id=runtime_result.document_id,
            )
            stored_file = self._lkpd_storage.save_pdf(pdf_bytes)
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
            await self._job_store.update_job(
                job.job_id,
                status="succeeded",
                clear_last_error=True,
            )
        except Exception as exc:
            callback_payload = LkpdWebhookResultPayload(
                job_id=job.job_id,
                status="failed_processing",
                user_id=job.user_id,
                error=CallbackErrorInfo(
                    code=self._map_error_code(exc),
                    message=str(exc),
                ),
                attempt=1,
                finished_at=finished_at,
            )
            await self._job_store.update_job(
                job.job_id,
                status="failed_processing",
                last_error=str(exc),
            )

        delivered = await self._deliver_with_retry(job=job, payload=callback_payload)
        if not delivered:
            await self._job_store.update_job(
                job.job_id,
                status="failed_delivery",
                last_error="Callback delivery failed after max retries.",
            )

    async def _deliver_with_retry(
        self,
        *,
        job: QueuedJob,
        payload: Any,
    ) -> bool:
        max_retries = settings.webhook_callback_max_retries
        backoffs = list(settings.webhook_callback_backoff_seconds)
        total_attempts = max_retries + 1

        for attempt in range(1, total_attempts + 1):
            payload.attempt = attempt
            try:
                await self._callback_client.send_json(
                    callback_url=str(job.callback_url),
                    payload=payload.model_dump(mode="json", exclude_none=True),
                )
                await self._job_store.update_job(
                    job.job_id,
                    callback_attempts=attempt,
                    clear_last_error=True,
                )
                return True
            except Exception as exc:
                await self._job_store.update_job(
                    job.job_id,
                    callback_attempts=attempt,
                    last_error=str(exc),
                )
                logger.warning(
                    "Callback delivery attempt %s/%s failed for job %s: %s",
                    attempt,
                    total_attempts,
                    job.job_id,
                    exc,
                )
                if attempt >= total_attempts:
                    return False

                delay = backoffs[min(attempt - 1, len(backoffs) - 1)]
                jitter = random.uniform(0, 0.5)
                await asyncio.sleep(delay + jitter)

        return False

    @staticmethod
    def _map_error_code(exc: Exception) -> str:
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
