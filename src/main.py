from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from starlette.responses import Response

from src.agent.callback import WebhookCallbackClient
from src.agent.jobs import MaterialJobStore
from src.agent.lkpd_storage import LkpdFileStorage
from src.agent.runtime import AgentRuntime
from src.agent.worker import MaterialJobWorker
from src.api import build_lkpd_router, build_material_router, build_oauth_router
from src.auth.revocation import shutdown_token_denylist
from src.core.api_response import (
    attach_meta_to_json_response,
    build_request_id,
)
from src.core.constants import APP_NAME, APP_VERSION
from src.core.exceptions import register_exception_handlers
from src.core.logging import configure_logging


configure_logging()

agent_runtime = AgentRuntime()
job_store = MaterialJobStore()
callback_client = WebhookCallbackClient()
lkpd_storage = LkpdFileStorage()
job_worker = MaterialJobWorker(
    runtime=agent_runtime,
    job_store=job_store,
    callback_client=callback_client,
    lkpd_storage=lkpd_storage,
)


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    await agent_runtime.initialize()
    await job_store.initialize()
    await callback_client.initialize()
    await lkpd_storage.initialize()
    job_worker.start()
    try:
        yield
    finally:
        await job_worker.stop()
        await callback_client.shutdown()
        await shutdown_token_denylist()
        await job_store.shutdown()
        await agent_runtime.shutdown()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=app_lifespan)


app.include_router(build_material_router(job_store))
app.include_router(build_lkpd_router(job_store, lkpd_storage))
app.include_router(build_oauth_router())


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = build_request_id()
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api"):
        return attach_meta_to_json_response(response, request_id)
    return response


register_exception_handlers(app)
