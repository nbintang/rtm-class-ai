from __future__ import annotations

import base64
from datetime import UTC, datetime
from uuid import uuid4

from src.agent.types import (
    JobKind,
    JobStatus,
    LkpdAsyncSubmitRequest,
    MaterialAsyncSubmitRequest,
    QueuedJob,
)
from src.config import settings


class MaterialJobStore:
    def __init__(self) -> None:
        self._redis = None

    async def initialize(self) -> None:
        if self._redis is not None:
            return

        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError(
                "redis package is required for async material queue."
            ) from exc

        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        await self._redis.ping()

    async def shutdown(self) -> None:
        if self._redis is None:
            return
        await self._redis.close()
        self._redis = None

    async def enqueue_job(
        self,
        *,
        job_kind: JobKind,
        request: MaterialAsyncSubmitRequest | LkpdAsyncSubmitRequest,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
    ) -> str:
        await self.initialize()
        assert self._redis is not None

        now = datetime.now(UTC)
        job_id = f"job-{uuid4().hex}"
        encoded_file = base64.b64encode(file_bytes).decode("ascii")

        if job_kind == "material":
            request_payload = request.to_material_upload_request().model_dump(mode="json")
        elif job_kind == "lkpd":
            request_payload = request.to_lkpd_upload_request().model_dump(mode="json")
        else:
            raise ValueError(f"Unsupported job_kind: {job_kind}")

        job = QueuedJob(
            job_id=job_id,
            job_kind=job_kind,
            status="accepted",
            user_id=request.user_id,
            callback_url=request.callback_url,
            request_payload=request_payload,
            filename=filename,
            content_type=content_type,
            file_b64=encoded_file,
            callback_attempts=0,
            created_at=now,
            updated_at=now,
        )
        await self._save_job(job)
        # LPUSH + BRPOP gives FIFO semantics.
        await self._redis.lpush(self._queue_key(job_kind), job_id)
        return job_id

    async def pop_next_job(self, *, timeout_seconds: int = 1) -> QueuedJob | None:
        await self.initialize()
        assert self._redis is not None

        queue_keys = [settings.job_queue_key, settings.lkpd_job_queue_key]
        popped = await self._redis.brpop(queue_keys, timeout=timeout_seconds)
        if not popped:
            return None

        _, job_id = popped
        return await self.get_job(job_id)

    async def get_job(self, job_id: str) -> QueuedJob | None:
        await self.initialize()
        assert self._redis is not None

        payload = await self._redis.get(self._job_key(job_id))
        if not payload:
            return None
        return QueuedJob.model_validate_json(payload)

    async def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        callback_attempts: int | None = None,
        last_error: str | None = None,
        clear_last_error: bool = False,
    ) -> QueuedJob | None:
        job = await self.get_job(job_id)
        if job is None:
            return None

        if status is not None:
            job.status = status
        if callback_attempts is not None:
            job.callback_attempts = callback_attempts
        if clear_last_error:
            job.last_error = None
        elif last_error is not None:
            job.last_error = last_error

        job.updated_at = datetime.now(UTC)
        await self._save_job(job)
        return job

    @staticmethod
    def decode_file_bytes(job: QueuedJob) -> bytes:
        return base64.b64decode(job.file_b64.encode("ascii"))

    async def _save_job(self, job: QueuedJob) -> None:
        assert self._redis is not None
        await self._redis.set(
            self._job_key(job.job_id),
            job.model_dump_json(),
            ex=settings.job_ttl_seconds,
        )

    @staticmethod
    def _queue_key(job_kind: JobKind) -> str:
        if job_kind == "material":
            return settings.job_queue_key
        return settings.lkpd_job_queue_key

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"material_jobs:{job_id}"
