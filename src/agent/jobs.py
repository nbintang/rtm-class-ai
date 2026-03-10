from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
from redis.asyncio import Redis as _Redis

from src.agent.types import (
    JobKind,
    JobStatus,
    LkpdAsyncSubmitRequest,
    MaterialAsyncSubmitRequest,
    QueuedJob,
)
from src.config import settings

logger = logging.getLogger(__name__)


class MaterialJobStore:
    def __init__(self) -> None:
        self._redis: _Redis | None = None
        self._db_pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        if self._redis is None:
            if _Redis is None:
                raise RuntimeError("redis package is required for async material queue.")

            self._redis = _Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            await self._redis.ping()

        if self._db_pool is None and settings.db_host:
            try:
                self._db_pool = await asyncpg.create_pool(
                    host=settings.db_host,
                    port=settings.db_port,
                    user=settings.db_user,
                    password=settings.db_pass,
                    database=settings.db_name,
                    min_size=1,
                    max_size=10,
                )
                logger.info("Postgres pool initialized for AIJob store")
            except Exception as exc:
                logger.warning("Failed to initialize Postgres pool: %s", exc)

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        if self._db_pool is not None:
            await self._db_pool.close()
            self._db_pool = None

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
        encoded_file = base64.b64encode(file_bytes).decode("ascii")

        # IDs for AIJob tracking
        if job_kind == "material":
            assert isinstance(request, MaterialAsyncSubmitRequest)
            request_payload = request.to_material_upload_request().model_dump(mode="json")
            job_id = request.job_id
            material_id = request.material_id
            requested_by_id = request.requested_by_id
        elif job_kind == "lkpd":
            assert isinstance(request, LkpdAsyncSubmitRequest)
            request_payload = request.to_lkpd_upload_request().model_dump(mode="json")
            job_id = f"job-{uuid4().hex}"
            material_id = str(uuid4())  # LKPD doesn't always have material_id in request
            requested_by_id = request.user_id
        else:
            raise ValueError(f"Unsupported job_kind: {job_kind}")

        job = QueuedJob(
            job_id=job_id,
            job_kind=job_kind,
            status="accepted",
            user_id=request.user_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
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
        await self._insert_to_postgres(job)

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

        # Update DB status if pool is available
        if status is not None:
            await self._update_postgres_status(job_id, status, job.last_error)

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

    async def _insert_to_postgres(self, job: QueuedJob) -> None:
        if self._db_pool is None:
            return

        try:
            job_id_uuid = self._ensure_uuid(job.job_id)
            material_id_uuid = self._ensure_uuid(job.material_id)
            requested_by_id_uuid = self._ensure_uuid(job.requested_by_id)

            job_type = "MCQ"
            if job.job_kind == "lkpd":
                job_type = "LKPD"
            else:
                gt = job.request_payload.get("generate_types", [])
                if gt:
                    t = gt[0].lower()
                    if t == "mcq": job_type = "MCQ"
                    elif t == "essay": job_type = "ESSAY"
                    elif t == "summary": job_type = "SUMMARY"

            params_json = json.dumps(job.request_payload)
            now = datetime.now(UTC)

            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO "AIJob" (
                        "id", "materialId", "requestedById", "type", "status",
                        "externalJobId", "createdAt", "updatedAt", "attempts", "parameters"
                    ) VALUES (
                        $1::uuid, $2::uuid, $3::uuid, 
                        $4::"AIJobType", $5::"AIJobStatus", 
                        $6::text, $7, $8, $9, $10
                    )
                    ON CONFLICT ("id") DO NOTHING
                    """,
                    job_id_uuid,
                    material_id_uuid,
                    requested_by_id_uuid,
                    job_type,
                    "accepted",
                    job.job_id,
                    job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=UTC),
                    job.updated_at if job.updated_at.tzinfo else job.updated_at.replace(tzinfo=UTC),
                    0,
                    params_json
                )
                logger.info("Job %s inserted into Postgres successfully", job.job_id)
        except Exception as exc:
            logger.error("Failed to insert Job into Postgres: %s", exc)

    async def _update_postgres_status(self, job_id: str, status: str, last_error: str | None = None) -> None:
        if self._db_pool is None:
            return

        try:
            job_id_uuid = self._ensure_uuid(job_id)
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE "AIJob"
                    SET "status" = $1::"AIJobStatus", "updatedAt" = $2, "lastError" = $3
                    WHERE "id"::text = $4::text OR "externalJobId"::text = $5::text
                    """,
                    status, datetime.now(UTC), last_error, 
                    str(job_id_uuid), str(job_id)
                )
        except Exception as exc:
            logger.warning("Failed to update Job status in Postgres: %s", exc)

    @staticmethod
    def _ensure_uuid(val: str | None) -> UUID:
        """
        Returns a UUID object. If the input is not a valid UUID string,
        generates a stable UUID v5 based on the input string.
        """
        if not val:
            return uuid4()
        try:
            return UUID(val)
        except (ValueError, TypeError):
            # For human-readable IDs like 'job-xxxx', convert to stable UUID v5
            import uuid
            namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8') # DNS namespace
            return uuid.uuid5(namespace, val)

    @staticmethod
    def _parse_uuid(val: str | None) -> UUID | None:
        if not val:
            return None
        try:
            return UUID(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _queue_key(job_kind: JobKind) -> str:
        if job_kind == "material":
            return settings.job_queue_key
        return settings.lkpd_job_queue_key

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"material_jobs:{job_id}"
