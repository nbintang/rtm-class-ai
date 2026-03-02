from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.api_response import (
    build_error_response,
    error_code_from_status,
    normalize_exception_detail,
)


class ServiceError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        code: str | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return build_error_response(
            request,
            status_code=exc.status_code,
            code=exc.code or error_code_from_status(exc.status_code),
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        message, details = normalize_exception_detail(
            exc.detail,
            default_message="HTTP request failed.",
        )
        return build_error_response(
            request,
            status_code=exc.status_code,
            code=error_code_from_status(exc.status_code),
            message=message,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return build_error_response(
            request,
            status_code=422,
            code="validation_error",
            message="Request validation failed.",
            details=exc.errors(),
        )
