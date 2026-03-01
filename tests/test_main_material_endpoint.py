from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import agent_runtime, app, callback_client, job_store, job_worker, lkpd_storage


class MaterialAsyncEndpointTests(unittest.TestCase):
    @staticmethod
    def _common_lifespan_patches():
        return (
            patch.object(agent_runtime, "initialize", new=AsyncMock(return_value=None)),
            patch.object(agent_runtime, "shutdown", new=AsyncMock(return_value=None)),
            patch.object(job_store, "initialize", new=AsyncMock(return_value=None)),
            patch.object(job_store, "shutdown", new=AsyncMock(return_value=None)),
            patch.object(job_worker, "start", return_value=None),
            patch.object(job_worker, "stop", new=AsyncMock(return_value=None)),
            patch.object(callback_client, "initialize", new=AsyncMock(return_value=None)),
            patch.object(callback_client, "shutdown", new=AsyncMock(return_value=None)),
            patch.object(lkpd_storage, "initialize", new=AsyncMock(return_value=None)),
        )

    def test_happy_path_returns_202(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            job_store, "enqueue_job", new=AsyncMock(return_value="job-abc")
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/material",
                    data={
                        "user_id": "user-1",
                        "callback_url": "https://example.com/callback",
                        "generate_types": ["mcq", "summary"],
                    },
                    files={"file": ("materi.txt", b"konten materi", "text/plain")},
                )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json(),
            {
                "job_id": "job-abc",
                "status": "accepted",
                "message": "Material queued for async processing.",
            },
        )

    def test_missing_callback_url_returns_422(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
            with TestClient(app) as client:
                response = client.post(
                    "/api/material",
                    data={
                        "user_id": "user-1",
                        "generate_types": ["summary"],
                    },
                    files={"file": ("materi.txt", b"konten materi", "text/plain")},
                )

        self.assertEqual(response.status_code, 422)

    def test_enqueue_failure_returns_503(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            job_store,
            "enqueue_job",
            new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/material",
                    data={
                        "user_id": "user-1",
                        "callback_url": "https://example.com/callback",
                        "generate_types": ["summary"],
                    },
                    files={"file": ("materi.txt", b"konten materi", "text/plain")},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("Failed to enqueue material job", response.json()["detail"])

    def test_old_webhook_route_removed(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
            with TestClient(app) as client:
                response = client.post(
                    "/webhook/material",
                    json={"user_id": "u"},
                )

        self.assertEqual(response.status_code, 404)

    def test_lkpd_submit_returns_202(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            job_store, "enqueue_job", new=AsyncMock(return_value="job-lkpd-123")
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/lkpd",
                    data={
                        "user_id": "user-1",
                        "callback_url": "https://example.com/callback-lkpd",
                        "activity_count": "5",
                    },
                    files={"file": ("materi.txt", b"konten materi", "text/plain")},
                )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json(),
            {
                "job_id": "job-lkpd-123",
                "status": "accepted",
                "message": "LKPD queued for async processing.",
            },
        )

    def test_lkpd_missing_callback_url_returns_422(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
            with TestClient(app) as client:
                response = client.post(
                    "/api/lkpd",
                    data={
                        "user_id": "user-1",
                        "activity_count": "5",
                    },
                    files={"file": ("materi.txt", b"konten materi", "text/plain")},
                )

        self.assertEqual(response.status_code, 422)

    def test_lkpd_download_returns_pdf(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            lkpd_storage, "get_pdf_path", return_value=Path("README.md")
        ):
            with TestClient(app) as client:
                response = client.get("/api/lkpd/files/lkpd-file-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/pdf")

    def test_lkpd_download_404_when_missing(self) -> None:
        patches = self._common_lifespan_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            lkpd_storage, "get_pdf_path", return_value=None
        ):
            with TestClient(app) as client:
                response = client.get("/api/lkpd/files/not-found")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
