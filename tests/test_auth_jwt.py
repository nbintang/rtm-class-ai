from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from src.auth.jwt import decode_and_verify_jwt, require_jwt
from src.config import settings


def _build_token(
    *,
    secret: str,
    iss: str,
    aud: str,
    sub: str = "client:test-client",
    expires_in_seconds: int = 300,
    scope: str = "material:write lkpd:write lkpd:read",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "scope": scope,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _set_jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 32)
    monkeypatch.setattr(settings, "jwt_issuer", "my-backend")
    monkeypatch.setattr(settings, "jwt_audience", "rtm-class-ai")
    monkeypatch.setattr(settings, "jwt_clock_skew_seconds", 0)
    monkeypatch.setattr(settings, "jwt_denylist_enabled", False)


def test_decode_and_verify_jwt_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_settings(monkeypatch)
    token = _build_token(
        secret=settings.jwt_secret,
        iss=settings.jwt_issuer,
        aud=settings.jwt_audience,
    )

    payload = decode_and_verify_jwt(token)

    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience
    assert payload["sub"] == "client:test-client"


def test_decode_and_verify_jwt_wrong_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_settings(monkeypatch)
    token = _build_token(
        secret=settings.jwt_secret,
        iss="not-backend",
        aud=settings.jwt_audience,
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_and_verify_jwt(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token issuer."


def test_decode_and_verify_jwt_wrong_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_settings(monkeypatch)
    token = _build_token(
        secret=settings.jwt_secret,
        iss=settings.jwt_issuer,
        aud="other-service",
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_and_verify_jwt(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token audience."


def test_decode_and_verify_jwt_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_settings(monkeypatch)
    token = _build_token(
        secret=settings.jwt_secret,
        iss=settings.jwt_issuer,
        aud=settings.jwt_audience,
        expires_in_seconds=-1,
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_and_verify_jwt(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token."


def test_require_jwt_missing_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_settings(monkeypatch)
    token = _build_token(
        secret=settings.jwt_secret,
        iss=settings.jwt_issuer,
        aud=settings.jwt_audience,
        scope="lkpd:read",
    )
    dependency = require_jwt(["material:write"])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(authorization=f"Bearer {token}"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient scope."


def test_require_jwt_invalid_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_settings(monkeypatch)
    token = _build_token(
        secret=settings.jwt_secret,
        iss=settings.jwt_issuer,
        aud=settings.jwt_audience,
        sub="service:backend",
    )
    dependency = require_jwt(["material:write"])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(authorization=f"Bearer {token}"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token subject."
