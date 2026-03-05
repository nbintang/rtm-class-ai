from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from src.agent.callback import WebhookCallbackClient
from src.agent.jobs import MaterialJobStore
from src.agent.types import QueuedJob
from src.config import settings


async def deliver_with_retry(
    *,
    callback_client: WebhookCallbackClient,
    job_store: MaterialJobStore,
    job: QueuedJob,
    payload: Any,
    logger: logging.Logger,
) -> bool:
    if not job.callback_url:
        logger.info(
            "Skipping callback delivery for job %s because callback_url is empty.",
            job.job_id,
        )
        return True

    max_retries = settings.webhook_callback_max_retries
    backoffs = list(settings.webhook_callback_backoff_seconds)
    total_attempts = max_retries + 1

    for attempt in range(1, total_attempts + 1):
        payload.attempt = attempt
        try:
            await callback_client.send_json(
                callback_url=str(job.callback_url),
                payload=payload.model_dump(mode="json", exclude_none=True),
            )
            await job_store.update_job(
                job.job_id,
                callback_attempts=attempt,
                clear_last_error=True,
            )
            return True
        except Exception as exc:
            error_message = _format_delivery_error(exc)
            error_type = exc.__class__.__name__
            retryable = _is_retryable_delivery_error(exc)
            await job_store.update_job(
                job.job_id,
                callback_attempts=attempt,
                last_error=error_message,
            )
            if attempt >= total_attempts or not retryable:
                logger.warning(
                    (
                        "Callback delivery attempt %s/%s failed for job %s (%s). "
                        "retryable=%s, error_type=%s, error=%s"
                    ),
                    attempt,
                    total_attempts,
                    job.job_id,
                    job.callback_url,
                    retryable,
                    error_type,
                    error_message,
                )
            else:
                delay = backoffs[min(attempt - 1, len(backoffs) - 1)]
                jitter = random.uniform(0, 0.5)
                sleep_seconds = delay + jitter
                logger.warning(
                    (
                        "Callback delivery attempt %s/%s failed for job %s (%s). "
                        "retryable=%s, error_type=%s, next_retry_in=%.2fs, error=%s"
                    ),
                    attempt,
                    total_attempts,
                    job.job_id,
                    job.callback_url,
                    retryable,
                    error_type,
                    sleep_seconds,
                    error_message,
                )
                await asyncio.sleep(sleep_seconds)
                continue

            if not retryable:
                return False
            logger.warning(
                "Callback delivery exhausted for job %s after %s attempt(s).",
                job.job_id,
                attempt,
            )
            return False

    return False


def _is_retryable_delivery_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {408, 425, 429}:
            return True
        if 500 <= status_code <= 599:
            return True
        return False
    if isinstance(exc, httpx.RequestError):
        return True
    return True


def _format_delivery_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        body_preview = exc.response.text.strip().replace("\n", " ")
        if body_preview:
            body_preview = body_preview[:300]
            return f"HTTPStatusError: status={status_code}, body={body_preview}"
        return f"HTTPStatusError: status={status_code}"

    message = str(exc).strip()
    if message:
        return f"{exc.__class__.__name__}: {message}"
    return exc.__class__.__name__

