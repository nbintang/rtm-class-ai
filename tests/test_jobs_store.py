from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agent.jobs import MaterialJobStore
from src.agent.types import LkpdAsyncSubmitRequest, MaterialAsyncSubmitRequest
from src.config import settings


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.queues: dict[str, list[str]] = {}

    async def ping(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.kv[key] = value

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def lpush(self, key: str, value: str) -> None:
        queue = self.queues.setdefault(key, [])
        queue.insert(0, value)

    async def brpop(self, keys: list[str] | str, timeout: int = 0) -> tuple[str, str] | None:
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            queue = self.queues.setdefault(key, [])
            if queue:
                value = queue.pop()
                return key, value
        return None


class MaterialJobStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_and_pop_job(self) -> None:
        store = MaterialJobStore()
        store._redis = FakeRedis()

        request = MaterialAsyncSubmitRequest(
            user_id="user-1",
            callback_url="https://example.com/callback",
            generate_types=["summary"],
        )

        with patch.object(settings, "job_queue_key", "material_jobs:queue"), patch.object(
            settings, "job_ttl_seconds", 86400
        ):
            job_id = await store.enqueue_job(
                job_kind="material",
                request=request,
                file_bytes=b"hello",
                filename="materi.txt",
                content_type="text/plain",
            )
            self.assertTrue(job_id.startswith("job-"))

            job = await store.pop_next_job(timeout_seconds=1)
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job.job_id, job_id)
            self.assertEqual(job.status, "accepted")
            self.assertEqual(job.job_kind, "material")
            self.assertEqual(store.decode_file_bytes(job), b"hello")

    async def test_update_job_status(self) -> None:
        store = MaterialJobStore()
        store._redis = FakeRedis()

        request = MaterialAsyncSubmitRequest(
            user_id="user-1",
            callback_url="https://example.com/callback",
            generate_types=["mcq"],
        )

        with patch.object(settings, "job_queue_key", "material_jobs:queue"), patch.object(
            settings, "job_ttl_seconds", 86400
        ):
            job_id = await store.enqueue_job(
                job_kind="material",
                request=request,
                file_bytes=b"data",
                filename="materi.txt",
                content_type="text/plain",
            )
            await store.update_job(
                job_id,
                status="processing",
                callback_attempts=2,
                last_error="timeout",
            )
            job = await store.get_job(job_id)
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job.status, "processing")
            self.assertEqual(job.callback_attempts, 2)
            self.assertEqual(job.last_error, "timeout")

    async def test_enqueue_lkpd_job_uses_lkpd_queue(self) -> None:
        store = MaterialJobStore()
        fake_redis = FakeRedis()
        store._redis = fake_redis
        request = LkpdAsyncSubmitRequest(
            user_id="user-2",
            callback_url="https://example.com/lkpd-callback",
            activity_count=5,
        )

        with patch.object(settings, "job_queue_key", "material_jobs:queue"), patch.object(
            settings, "lkpd_job_queue_key", "lkpd_jobs:queue"
        ), patch.object(settings, "job_ttl_seconds", 86400):
            job_id = await store.enqueue_job(
                job_kind="lkpd",
                request=request,
                file_bytes=b"data-lkpd",
                filename="materi-lkpd.txt",
                content_type="text/plain",
            )

            self.assertIn("lkpd_jobs:queue", fake_redis.queues)
            popped = await store.pop_next_job(timeout_seconds=1)
            self.assertIsNotNone(popped)
            assert popped is not None
            self.assertEqual(popped.job_id, job_id)
            self.assertEqual(popped.job_kind, "lkpd")


if __name__ == "__main__":
    unittest.main()
