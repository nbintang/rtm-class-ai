from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.agent.types import MaterialWebhookResultPayload, QueuedJob
from src.agent.worker_helpers.delivery import deliver_with_retry
from src.config import settings


class DummyCallbackClient:
    def __init__(self, outcomes: list[Exception | None]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def send_json(self, *, callback_url: str, payload: dict) -> None:
        _ = callback_url, payload
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if outcome is not None:
            raise outcome


class DummyJobStore:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    async def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        callback_attempts: int | None = None,
        last_error: str | None = None,
        clear_last_error: bool = False,
    ) -> dict[str, Any]:
        update = {
            "job_id": job_id,
            "status": status,
            "callback_attempts": callback_attempts,
            "last_error": last_error,
            "clear_last_error": clear_last_error,
        }
        self.updates.append(update)
        return update


def _build_job(callback_url: str | None = "https://example.com/callback") -> QueuedJob:
    now = datetime.now(UTC)
    return QueuedJob(
        job_id="job-test-1",
        job_kind="material",
        status="accepted",
        user_id="user-1",
        callback_url=callback_url,
        request_payload={},
        filename="material.txt",
        content_type="text/plain",
        file_b64="aGVsbG8=",
        callback_attempts=0,
        created_at=now,
        updated_at=now,
    )


def _build_payload() -> MaterialWebhookResultPayload:
    return MaterialWebhookResultPayload(
        job_id="job-test-1",
        status="succeeded",
        user_id="user-1",
        result={
            "user_id": "user-1",
            "document_id": "doc-1",
            "material": {
                "filename": "material.txt",
                "file_type": "txt",
                "extracted_chars": 5,
            },
            "mcq_quiz": None,
            "essay_quiz": None,
            "summary": None,
            "sources": [],
            "tool_calls": [],
            "warnings": [],
        },
        attempt=1,
        finished_at=datetime.now(UTC),
    )


def test_retry_then_success(monkeypatch) -> None:
    import src.agent.worker_helpers.delivery as delivery_module

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(delivery_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(settings, "webhook_callback_max_retries", 2)
    monkeypatch.setattr(settings, "webhook_callback_backoff_seconds", (0,))

    request = httpx.Request("POST", "https://example.com/callback")
    callback_client = DummyCallbackClient([httpx.ReadTimeout("", request=request), None])
    job_store = DummyJobStore()
    logger = logging.getLogger("test")

    delivered = asyncio.run(
        deliver_with_retry(
            callback_client=callback_client,
            job_store=job_store,
            job=_build_job(),
            payload=_build_payload(),
            logger=logger,
        )
    )

    assert delivered is True
    assert callback_client.calls == 2
    assert job_store.updates[0]["callback_attempts"] == 1
    assert job_store.updates[1]["callback_attempts"] == 2
    assert job_store.updates[1]["clear_last_error"] is True


def test_non_retryable_http_400_stops_immediately(monkeypatch) -> None:
    monkeypatch.setattr(settings, "webhook_callback_max_retries", 3)
    monkeypatch.setattr(settings, "webhook_callback_backoff_seconds", (0,))

    request = httpx.Request("POST", "https://example.com/callback")
    response = httpx.Response(400, request=request, text="bad request")
    error = httpx.HTTPStatusError("400 error", request=request, response=response)
    callback_client = DummyCallbackClient([error])
    job_store = DummyJobStore()
    logger = logging.getLogger("test")

    delivered = asyncio.run(
        deliver_with_retry(
            callback_client=callback_client,
            job_store=job_store,
            job=_build_job(),
            payload=_build_payload(),
            logger=logger,
        )
    )

    assert delivered is False
    assert callback_client.calls == 1
    assert len(job_store.updates) == 1
    assert "status=400" in (job_store.updates[0]["last_error"] or "")


def test_timeout_error_has_non_empty_last_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "webhook_callback_max_retries", 0)
    monkeypatch.setattr(settings, "webhook_callback_backoff_seconds", (0,))

    request = httpx.Request("POST", "https://example.com/callback")
    callback_client = DummyCallbackClient([httpx.ReadTimeout("", request=request)])
    job_store = DummyJobStore()
    logger = logging.getLogger("test")

    delivered = asyncio.run(
        deliver_with_retry(
            callback_client=callback_client,
            job_store=job_store,
            job=_build_job(),
            payload=_build_payload(),
            logger=logger,
        )
    )

    assert delivered is False
    assert "ReadTimeout" in (job_store.updates[0]["last_error"] or "")


def test_missing_callback_url_skips_delivery() -> None:
    callback_client = DummyCallbackClient([None])
    job_store = DummyJobStore()
    logger = logging.getLogger("test")

    delivered = asyncio.run(
        deliver_with_retry(
            callback_client=callback_client,
            job_store=job_store,
            job=_build_job(callback_url=None),
            payload=_build_payload(),
            logger=logger,
        )
    )

    assert delivered is True
    assert callback_client.calls == 0
    assert job_store.updates == []
