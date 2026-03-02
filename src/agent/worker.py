from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from src.agent.callback import WebhookCallbackClient
from src.agent.jobs import MaterialJobStore
from src.agent.lkpd_storage import LkpdFileStorage
from src.agent.runtime import AgentRuntime
from src.agent.types import QueuedJob
from src.agent.worker_helpers.delivery import deliver_with_retry
from src.agent.worker_helpers.job_handlers import (
    process_lkpd_job,
    process_material_job,
)


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
        callback_payload = await process_material_job(
            runtime=self._runtime,
            job_store=self._job_store,
            job=job,
        )
        delivered = await self._deliver_with_retry(job=job, payload=callback_payload)
        if not delivered:
            await self._job_store.update_job(
                job.job_id,
                status="failed_delivery",
                last_error="Callback delivery failed after max retries.",
            )

    async def _process_lkpd_job(self, job: QueuedJob) -> None:
        callback_payload = await process_lkpd_job(
            runtime=self._runtime,
            job_store=self._job_store,
            lkpd_storage=self._lkpd_storage,
            job=job,
        )
        delivered = await self._deliver_with_retry(job=job, payload=callback_payload)
        if not delivered:
            await self._job_store.update_job(
                job.job_id,
                status="failed_delivery",
                last_error="Callback delivery failed after max retries.",
            )

    async def _deliver_with_retry(self, *, job: QueuedJob, payload: object) -> bool:
        return await deliver_with_retry(
            callback_client=self._callback_client,
            job_store=self._job_store,
            job=job,
            payload=payload,
            logger=logger,
        )

