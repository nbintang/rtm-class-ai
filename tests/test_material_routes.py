from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.material_routes import build_material_router
from src.config import settings
from src.core.exceptions import register_exception_handlers


class DummyMaterialJobStore:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def enqueue_job(
        self,
        *,
        job_kind: str,
        request: Any,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
    ) -> str:
        self.calls.append(
            {
                "job_kind": job_kind,
                "request": request,
                "file_bytes": file_bytes,
                "filename": filename,
                "content_type": content_type,
            }
        )
        return "job-test-123"


@pytest.fixture
def app_and_store(monkeypatch: pytest.MonkeyPatch) -> tuple[FastAPI, DummyMaterialJobStore]:
    monkeypatch.setattr(settings, "jwt_enabled", False)
    monkeypatch.setattr(settings, "material_max_file_mb", 15)
    store = DummyMaterialJobStore()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(build_material_router(store))
    return app, store


@pytest.mark.parametrize(
    ("path", "extra_form", "expected_type", "expected_message"),
    [
        ("/api/mcq", {"mcq_count": "8"}, "mcq", "MCQ queued for async processing."),
        ("/api/essay", {"essay_count": "4"}, "essay", "Essay queued for async processing."),
        (
            "/api/summary",
            {"summary_max_words": "180"},
            "summary",
            "Summary queued for async processing.",
        ),
    ],
)
def test_single_generation_endpoints_enqueue_one_type(
    app_and_store: tuple[FastAPI, DummyMaterialJobStore],
    path: str,
    extra_form: dict[str, str],
    expected_type: str,
    expected_message: str,
) -> None:
    app, store = app_and_store
    client = TestClient(app)
    data = {
        "user_id": "user-1",
        "callback_url": "https://example.com/hooks/material",
        "mcp_enabled": "true",
        **extra_form,
    }
    files = {"file": ("materi.txt", b"hello world", "text/plain")}

    response = client.post(path, data=data, files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["job_id"] == "job-test-123"
    assert body["message"] == expected_message

    assert len(store.calls) == 1
    call = store.calls[0]
    assert call["job_kind"] == "material"
    assert call["request"].generate_types == [expected_type]
    assert call["filename"] == "materi.txt"


def test_material_endpoint_still_supports_multiple_generate_types(
    app_and_store: tuple[FastAPI, DummyMaterialJobStore],
) -> None:
    app, store = app_and_store
    client = TestClient(app)
    files = {"file": ("materi.txt", b"hello world", "text/plain")}
    data = [
        ("user_id", "user-1"),
        ("callback_url", "https://example.com/hooks/material"),
        ("generate_types", "mcq"),
        ("generate_types", "essay"),
        ("generate_types", "summary"),
        ("mcq_count", "10"),
        ("essay_count", "3"),
        ("summary_max_words", "200"),
        ("mcp_enabled", "true"),
    ]

    response = client.post("/api/material", data=data, files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Material queued for async processing."

    assert len(store.calls) == 1
    assert store.calls[0]["request"].generate_types == ["mcq", "essay", "summary"]


def test_mcq_validation_error_uses_api_error_envelope(
    app_and_store: tuple[FastAPI, DummyMaterialJobStore],
) -> None:
    app, _ = app_and_store
    client = TestClient(app)
    files = {"file": ("materi.txt", b"hello world", "text/plain")}
    data = {
        "user_id": "user-1",
        "callback_url": "https://example.com/hooks/material",
        "mcq_count": "0",
    }

    response = client.post("/api/mcq", data=data, files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed."


@pytest.mark.parametrize(
    ("path", "data"),
    [
        (
            "/api/material",
            [
                ("user_id", "user-1"),
                ("callback_url", "https://example.com/hooks/material"),
                ("generate_types", "mcq"),
                ("mcp_enabled", "true"),
            ],
        ),
        (
            "/api/mcq",
            {
                "user_id": "user-1",
                "callback_url": "https://example.com/hooks/material",
                "mcq_count": "10",
                "mcp_enabled": "true",
            },
        ),
        (
            "/api/essay",
            {
                "user_id": "user-1",
                "callback_url": "https://example.com/hooks/material",
                "essay_count": "3",
                "mcp_enabled": "true",
            },
        ),
        (
            "/api/summary",
            {
                "user_id": "user-1",
                "callback_url": "https://example.com/hooks/material",
                "summary_max_words": "200",
                "mcp_enabled": "true",
            },
        ),
    ],
)
def test_material_endpoints_reject_empty_file_with_validation_error(
    app_and_store: tuple[FastAPI, DummyMaterialJobStore],
    path: str,
    data: list[tuple[str, str]] | dict[str, str],
) -> None:
    app, store = app_and_store
    client = TestClient(app)
    files = {"file": ("empty.txt", b"", "text/plain")}

    response = client.post(path, data=data, files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed."
    assert body["error"]["details"][0]["loc"] == ["body", "file"]
    assert body["error"]["details"][0]["msg"] == "Uploaded file must not be empty."
    assert store.calls == []
