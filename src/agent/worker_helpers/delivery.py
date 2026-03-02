from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

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
            await job_store.update_job(
                job.job_id,
                callback_attempts=attempt,
                last_error=str(exc),
            )
            logger.warning(
                "Callback delivery attempt %s/%s failed for job %s: %s",
                attempt,
                total_attempts,
                job.job_id,
                exc,
            )
            if attempt >= total_attempts:
                return False

            delay = backoffs[min(attempt - 1, len(backoffs) - 1)]
            jitter = random.uniform(0, 0.5)
            await asyncio.sleep(delay + jitter)

    return False

