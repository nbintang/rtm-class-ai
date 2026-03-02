from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import Any, Annotated

import jwt
from fastapi import Header, HTTPException, status
from jwt import InvalidTokenError

from src.config import settings


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if not hmac.compare_digest(scheme.lower(), "bearer") or not token.strip():
        raise _unauthorized("Invalid Authorization header.")
    return token.strip()


def _audience_matches(expected: str, claim: Any) -> bool:
    if isinstance(claim, str):
        return hmac.compare_digest(claim, expected)

    if isinstance(claim, list):
        return any(isinstance(item, str) and hmac.compare_digest(item, expected) for item in claim)

    return False


def _extract_scope_set(payload: dict[str, Any]) -> set[str]:
    raw_scope = payload.get("scope")
    if isinstance(raw_scope, str):
        return {part for part in raw_scope.split(" ") if part}
    return set()


def decode_and_verify_jwt(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={
                "require": ["iss", "aud", "sub", "exp", "iat"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": False,
                "verify_aud": False,
            },
            leeway=settings.jwt_clock_skew_seconds,
        )
    except InvalidTokenError as exc:
        raise _unauthorized("Invalid or expired token.") from exc

    issuer = payload.get("iss")
    if not isinstance(issuer, str) or not hmac.compare_digest(issuer, settings.jwt_issuer):
        raise _unauthorized("Invalid token issuer.")

    if not _audience_matches(settings.jwt_audience, payload.get("aud")):
        raise _unauthorized("Invalid token audience.")

    return payload


def require_jwt(required_scopes: list[str] | None = None) -> Callable[..., dict[str, Any]]:
    async def dependency(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> dict[str, Any]:
        if not settings.jwt_enabled:
            return {}

        token = _extract_bearer_token(authorization)
        payload = decode_and_verify_jwt(token)

        needed = set(required_scopes or [])
        if not needed:
            return payload

        provided_scopes = _extract_scope_set(payload)
        if not needed.issubset(provided_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient scope.",
            )
        return payload

    return dependency
