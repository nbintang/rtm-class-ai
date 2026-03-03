from __future__ import annotations

import hmac

from fastapi import APIRouter, Form, Request

from src.auth.jwt import issue_client_access_token
from src.auth.rate_limit import RateLimitExceededError, oauth_token_rate_limiter
from src.config import settings
from src.core.api_response import ApiSuccessResponse, build_success_payload
from src.core.exceptions import ServiceError
from src.api.schemas import OAuthTokenData


def build_oauth_error(
    *,
    error: str,
    message: str,
    status_code: int = 400,
) -> ServiceError:
    return ServiceError(
        message=message,
        status_code=status_code,
        code=error,
        details={
            "error": error,
            "error_description": message,
        },
    )


def normalize_scope_items(scope_raw: str | None) -> tuple[str, ...]:
    if scope_raw is None:
        return settings.oauth_default_scopes

    scope_text = scope_raw.strip()
    if not scope_text:
        return settings.oauth_default_scopes

    seen: set[str] = set()
    out: list[str] = []
    for part in scope_text.split():
        if part in seen:
            continue
        seen.add(part)
        out.append(part)
    return tuple(out)


def resolve_scopes(scope_raw: str | None) -> tuple[str, ...]:
    requested_scopes = normalize_scope_items(scope_raw)
    if not requested_scopes:
        raise build_oauth_error(
            error="invalid_request",
            message="No scopes available for token issuance.",
        )

    allowed = set(settings.oauth_allowed_scopes)
    if not set(requested_scopes).issubset(allowed):
        raise build_oauth_error(
            error="invalid_request",
            message="Requested scope is not allowed for this client.",
        )

    return requested_scopes


def is_valid_client(client_id: str, client_secret: str) -> bool:
    expected_id = settings.oauth_client_id
    expected_secret = settings.oauth_client_secret
    id_matches = hmac.compare_digest(client_id, expected_id)
    secret_matches = hmac.compare_digest(client_secret, expected_secret)
    return id_matches and secret_matches


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def build_oauth_router() -> APIRouter:
    router = APIRouter(tags=["oauth"])
    
    @router.post(
        "/api/oauth/token",
        response_model=ApiSuccessResponse[OAuthTokenData],
        response_model_exclude_none=True,
    )
    async def oauth_token(
        request: Request,
        grant_type: str | None = Form(default=None),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
        scope: str | None = Form(default=None),
    ) -> ApiSuccessResponse[OAuthTokenData]:
        if not settings.oauth_enabled:
            raise ServiceError("OAuth token endpoint is disabled.", status_code=404)

        try:
            oauth_token_rate_limiter.enforce(
                ip=client_ip(request),
                client_id=(client_id or "").strip() or "unknown",
            )
        except RateLimitExceededError as exc:
            raise build_oauth_error(
                error="too_many_requests",
                message=str(exc),
                status_code=429,
            ) from exc

        if not grant_type or not client_id or not client_secret:
            raise build_oauth_error(
                error="invalid_request",
                message="grant_type, client_id, and client_secret are required.",
            )

        grant_type_value = grant_type.strip()
        if not hmac.compare_digest(grant_type_value, "client_credentials"):
            raise build_oauth_error(
                error="invalid_request",
                message="Unsupported grant_type. Only client_credentials is supported.",
            )

        client_id_value = client_id.strip()
        if not client_id_value:
            raise build_oauth_error(
                error="invalid_request",
                message="client_id must not be empty.",
            )

        if not is_valid_client(client_id_value, client_secret):
            raise build_oauth_error(
                error="invalid_client",
                message="Invalid client credentials.",
            )

        scopes = resolve_scopes(scope)
        issued = issue_client_access_token(client_id_value, scopes)
        return build_success_payload(
            request=request,
            data=OAuthTokenData(
                access_token=issued.access_token,
                token_type=issued.token_type,
                expires_in=issued.expires_in,
                scope=issued.scope,
            ),
            message="Access token issued.",
        )

    return router
