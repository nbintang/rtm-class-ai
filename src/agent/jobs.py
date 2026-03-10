import base64
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
from redis.asyncio import Redis

from src.agent.types import (
    JobKind,
    JobStatus,
    LkpdAsyncSubmitRequest,
    MaterialAsyncSubmitRequest,
    QueuedJob,
)
from src.config import settings

logger = logging.getLogger(__name__)
from redis.asyncio import Redis as _Redis

class MaterialJobStore:
    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._db_pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        if self._redis is None:
            self._redis = Redis.from_url(
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
        generated_job_id = f"job-{uuid4().hex}"
        encoded_file = base64.b64encode(file_bytes).decode("ascii")

        if job_kind == "material":
            request_payload = request.to_material_upload_request().model_dump(mode="json")
            job_id = request.job_id
            material_id = request.material_id
            requested_by_id = request.requested_by_id
        elif job_kind == "lkpd":
            request_payload = request.to_lkpd_upload_request().model_dump(mode="json")
            job_id = generated_job_id
            material_id = None
            requested_by_id = None
        else:
            raise ValueError(f"Unsupported job_kind: {job_kind}")

        job = QueuedJob(
            job_id=job_id,
            material_id=material_id,
            job_kind=job_kind,
            status="accepted",
            user_id=request.user_id,
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

            # Parse UUIDs. Fallback to random UUID if invalid (though they should be valid)
            jid = self._parse_uuid(job.job_id)
            mid = self._parse_uuid(job.material_id)
            uid = self._parse_uuid(job.user_id)

            params_json = json.dumps(job.request_payload)

            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO "AIJob" (
                        "id", "materialId", "requestedById", "type", "status",
                        "externalJobId", "createdAt", "updatedAt", "attempts", "parameters"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT ("id") DO NOTHING
                    """,
                    jid, mid, uid, job_type, "accepted", 
                    job.job_id, job.created_at, job.updated_at, 0, params_json
                )
                logger.info("Job %s inserted into Postgres successfully", job.job_id)
        except Exception as exc:
            logger.error("Failed to insert Job into Postgres: %s", exc)

    @staticmethod
    def _parse_uuid(val: str) -> UUID:
        try:
            return UUID(val)
        except (ValueError, TypeError):
            return uuid4()

    @staticmethod
    def _queue_key(job_kind: JobKind) -> str:
        if job_kind == "material":
            return settings.job_queue_key
        return settings.lkpd_job_queue_key

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"material_jobs:{job_id}"
