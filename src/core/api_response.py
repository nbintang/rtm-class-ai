from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Generic, Literal, TypeVar
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.responses import Response

T = TypeVar("T")


class ApiMeta(BaseModel):
    request_id: str = Field(min_length=1)


class ApiErrorDetail(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: Any | None = None


class ApiSuccessResponse(BaseModel, Generic[T]):
    success: Literal[True] = True
    data: T
    message: str | None = None
    meta: ApiMeta


class ApiErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ApiErrorDetail
    meta: ApiMeta


ERROR_CODE_BY_STATUS: dict[int, str] = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    413: "payload_too_large",
    429: "too_many_requests",
    422: "validation_error",
    500: "internal_error",
    503: "service_unavailable",
}


def error_code_from_status(status_code: int) -> str:
    if status_code in ERROR_CODE_BY_STATUS:
        return ERROR_CODE_BY_STATUS[status_code]
    if status_code >= 500:
        return "internal_error"
    return "invalid_request"


def build_request_id() -> str:
    return f"req-{uuid4()}"


def get_or_set_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id

    request_id = build_request_id()
    request.state.request_id = request_id
    return request_id


def build_success_payload(
    request: Request,
    data: T,
    message: str | None = None,
) -> ApiSuccessResponse[T]:
    return ApiSuccessResponse[T](
        data=data,
        message=message,
        meta=ApiMeta(request_id=get_or_set_request_id(request)),
    )


def build_error_payload(
    request: Request,
    *,
    status_code: int,
    message: str,
    details: Any | None = None,
    code: str | None = None,
) -> ApiErrorResponse:
    return ApiErrorResponse(
        error=ApiErrorDetail(
            code=code or error_code_from_status(status_code),
            message=message,
            details=details,
        ),
        meta=ApiMeta(request_id=get_or_set_request_id(request)),
    )


def build_error_response(
    request: Request,
    *,
    status_code: int,
    message: str,
    details: Any | None = None,
    code: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    payload = build_error_payload(
        request,
        status_code=status_code,
        message=message,
        details=details,
        code=code,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers=dict(headers or {}),
    )


def normalize_exception_detail(
    detail: Any,
    *,
    default_message: str,
) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None

    if isinstance(detail, Mapping):
        raw_message = detail.get("message")
        if isinstance(raw_message, str) and raw_message:
            extra = {k: v for k, v in detail.items() if k != "message"}
            return raw_message, extra or None
        return default_message, dict(detail)

    if isinstance(detail, list):
        return default_message, detail

    if detail is None:
        return default_message, None

    return str(detail), None


def attach_meta_to_json_response(response: Response, request_id: str) -> Response:
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        return response

    body = getattr(response, "body", None)
    if not isinstance(body, (bytes, bytearray)):
        return response

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return response

    if not isinstance(payload, dict):
        return response

    raw_meta = payload.get("meta")
    if isinstance(raw_meta, Mapping):
        if raw_meta.get("request_id") == request_id:
            return response
        payload["meta"] = {**raw_meta, "request_id": request_id}
    else:
        payload["meta"] = {"request_id": request_id}

    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    response.body = encoded
    response.headers["content-length"] = str(len(encoded))
    return response
