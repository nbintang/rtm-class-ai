from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.agent.types import (
    LkpdActivity,
    LkpdContent,
    LkpdGenerateRuntimeResult,
    LkpdRubricItem,
    MaterialGenerateResponse,
    MaterialInfo,
    QueuedJob,
    SummaryContent,
)
from src.agent.worker import MaterialJobWorker
from src.config import settings


class DummyJobStore:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    async def update_job(self, job_id: str, **kwargs):
        self.updates.append({"job_id": job_id, **kwargs})
        return None

    @staticmethod
    def decode_file_bytes(_: QueuedJob) -> bytes:
        return b"abc"


class DummyCallbackClient:
    def __init__(self, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0
        self.payloads: list[dict] = []

    async def send_json(self, *, callback_url: str, payload: dict) -> None:
        self.calls += 1
        self.payloads.append(payload)
        if self.calls <= self.failures_before_success:
            raise RuntimeError("delivery failed")


class DummyLkpdStorage:
    def save_pdf(self, payload: bytes):
        del payload
        return type(
            "Stored",
            (),
            {
                "file_id": "lkpd-file-1",
                "expires_at": datetime.now(UTC) + timedelta(hours=24),
                "path": Path(".generated/lkpd/lkpd-file-1.pdf"),
            },
        )()

    def cleanup_expired_files(self) -> int:
        return 0


class MaterialJobWorkerTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _material_job() -> QueuedJob:
        return QueuedJob(
            job_id="job-1",
            job_kind="material",
            status="accepted",
            user_id="user-1",
            callback_url="https://example.com/callback",
            request_payload={
                "user_id": "user-1",
                "generate_types": ["summary"],
                "mcq_count": 10,
                "essay_count": 3,
                "summary_max_words": 200,
                "mcp_enabled": True,
            },
            filename="materi.txt",
            content_type="text/plain",
            file_b64="YWJj",
            callback_attempts=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def _lkpd_job() -> QueuedJob:
        return QueuedJob(
            job_id="job-lkpd-1",
            job_kind="lkpd",
            status="accepted",
            user_id="user-1",
            callback_url="https://example.com/lkpd-callback",
            request_payload={
                "user_id": "user-1",
                "activity_count": 2,
            },
            filename="materi.txt",
            content_type="text/plain",
            file_b64="YWJj",
            callback_attempts=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def test_process_material_job_success(self) -> None:
        runtime = AsyncMock()
        runtime.invoke_material_upload = AsyncMock(
            return_value=MaterialGenerateResponse(
                user_id="user-1",
                document_id="doc-1",
                material=MaterialInfo(
                    filename="materi.txt",
                    file_type="txt",
                    extracted_chars=3,
                ),
                summary=SummaryContent(
                    title="Ringkasan",
                    overview="Ini ringkasan.",
                    key_points=["Poin 1"],
                ),
            )
        )
        job_store = DummyJobStore()
        callback_client = DummyCallbackClient()
        worker = MaterialJobWorker(
            runtime=runtime,
            job_store=job_store,  # type: ignore[arg-type]
            callback_client=callback_client,  # type: ignore[arg-type]
            lkpd_storage=DummyLkpdStorage(),  # type: ignore[arg-type]
        )

        with patch.object(settings, "webhook_callback_max_retries", 3), patch.object(
            settings, "webhook_callback_backoff_seconds", (0, 0, 0)
        ), patch("src.agent.worker.random.uniform", return_value=0):
            await worker._process_job(self._material_job())

        self.assertGreaterEqual(callback_client.calls, 1)
        self.assertTrue(any(item.get("status") == "processing" for item in job_store.updates))
        self.assertTrue(any(item.get("status") == "succeeded" for item in job_store.updates))
        self.assertEqual(callback_client.payloads[0]["event"], "material.generated")

    async def test_process_material_job_failed_delivery_after_retries(self) -> None:
        runtime = AsyncMock()
        runtime.invoke_material_upload = AsyncMock(
            return_value=MaterialGenerateResponse(
                user_id="user-1",
                document_id="doc-1",
                material=MaterialInfo(
                    filename="materi.txt",
                    file_type="txt",
                    extracted_chars=3,
                ),
            )
        )
        job_store = DummyJobStore()
        callback_client = DummyCallbackClient(failures_before_success=99)
        worker = MaterialJobWorker(
            runtime=runtime,
            job_store=job_store,  # type: ignore[arg-type]
            callback_client=callback_client,  # type: ignore[arg-type]
            lkpd_storage=DummyLkpdStorage(),  # type: ignore[arg-type]
        )

        with patch.object(settings, "webhook_callback_max_retries", 3), patch.object(
            settings, "webhook_callback_backoff_seconds", (0, 0, 0)
        ), patch("src.agent.worker.random.uniform", return_value=0):
            await worker._process_job(self._material_job())

        self.assertEqual(callback_client.calls, 4)
        self.assertTrue(any(item.get("status") == "failed_delivery" for item in job_store.updates))

    async def test_process_material_job_failed_processing_callback_sent(self) -> None:
        runtime = AsyncMock()
        runtime.invoke_material_upload = AsyncMock(side_effect=RuntimeError("generation failed"))
        job_store = DummyJobStore()
        callback_client = DummyCallbackClient()
        worker = MaterialJobWorker(
            runtime=runtime,
            job_store=job_store,  # type: ignore[arg-type]
            callback_client=callback_client,  # type: ignore[arg-type]
            lkpd_storage=DummyLkpdStorage(),  # type: ignore[arg-type]
        )

        with patch.object(settings, "webhook_callback_max_retries", 3), patch.object(
            settings, "webhook_callback_backoff_seconds", (0, 0, 0)
        ), patch("src.agent.worker.random.uniform", return_value=0):
            await worker._process_job(self._material_job())

        self.assertEqual(callback_client.calls, 1)
        self.assertTrue(any(item.get("status") == "failed_processing" for item in job_store.updates))

    async def test_process_lkpd_job_success_sends_pdf_url(self) -> None:
        runtime = AsyncMock()
        runtime.invoke_lkpd_upload = AsyncMock(
            return_value=LkpdGenerateRuntimeResult(
                document_id="doc-lkpd-1",
                material=MaterialInfo(
                    filename="materi.txt",
                    file_type="txt",
                    extracted_chars=100,
                ),
                lkpd=LkpdContent(
                    title="LKPD Ekosistem",
                    learning_objectives=["Memahami ekosistem"],
                    instructions=["Baca materi", "Kerjakan soal"],
                    activities=[
                        LkpdActivity(
                            activity_no=1,
                            task="Identifikasi komponen biotik",
                            expected_output="Daftar komponen biotik",
                            assessment_hint="Akurasi klasifikasi",
                        ),
                        LkpdActivity(
                            activity_no=2,
                            task="Buat rantai makanan",
                            expected_output="Diagram rantai makanan",
                            assessment_hint="Kelengkapan tingkat trofik",
                        ),
                    ],
                    worksheet_template="Nama/Kelas/Jawaban",
                    assessment_rubric=[
                        LkpdRubricItem(
                            aspect="Konsep",
                            criteria="Ketepatan",
                            score_range="1-4",
                        )
                    ],
                ),
            )
        )
        job_store = DummyJobStore()
        callback_client = DummyCallbackClient()
        worker = MaterialJobWorker(
            runtime=runtime,
            job_store=job_store,  # type: ignore[arg-type]
            callback_client=callback_client,  # type: ignore[arg-type]
            lkpd_storage=DummyLkpdStorage(),  # type: ignore[arg-type]
        )

        with patch.object(settings, "app_public_base_url", "http://localhost:8000"), patch.object(
            settings, "webhook_callback_max_retries", 3
        ), patch.object(settings, "webhook_callback_backoff_seconds", (0, 0, 0)), patch(
            "src.agent.worker.render_lkpd_pdf", return_value=b"%PDF-1.4 test"
        ), patch(
            "src.agent.worker.random.uniform", return_value=0
        ):
            await worker._process_job(self._lkpd_job())

        self.assertEqual(callback_client.calls, 1)
        payload = callback_client.payloads[0]
        self.assertEqual(payload["event"], "lkpd.generated")
        self.assertEqual(payload["status"], "succeeded")
        self.assertIn("pdf_url", payload["result"])
        self.assertTrue(payload["result"]["pdf_url"].endswith("/api/lkpd/files/lkpd-file-1"))


if __name__ == "__main__":
    unittest.main()
