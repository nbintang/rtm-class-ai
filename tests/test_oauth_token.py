from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.oauth_routes import build_oauth_router
from src.auth.jwt import decode_and_verify_jwt
from src.auth.rate_limit import oauth_token_rate_limiter
from src.config import settings
from src.core.exceptions import register_exception_handlers


@pytest.fixture(autouse=True)
def _oauth_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "oauth_enabled", True)
    monkeypatch.setattr(settings, "oauth_client_id", "my-client")
    monkeypatch.setattr(settings, "oauth_client_secret", "my-secret")
    monkeypatch.setattr(
        settings,
        "oauth_allowed_scopes",
        ("material:write", "lkpd:write", "lkpd:read"),
    )
    monkeypatch.setattr(
        settings,
        "oauth_default_scopes",
        ("material:write", "lkpd:write", "lkpd:read"),
    )
    monkeypatch.setattr(settings, "oauth_token_ttl_seconds", 300)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 32)
    monkeypatch.setattr(settings, "jwt_issuer", "my-backend")
    monkeypatch.setattr(settings, "jwt_audience", "rtm-class-ai")
    monkeypatch.setattr(settings, "jwt_clock_skew_seconds", 0)
    oauth_token_rate_limiter.reset()
    yield
    oauth_token_rate_limiter.reset()


def _build_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(build_oauth_router())
    return TestClient(app)


def test_oauth_token_success_default_scope() -> None:
    client = _build_client()
    response = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "my-client",
            "client_secret": "my-secret",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Access token issued."
    assert body["data"]["token_type"] == "Bearer"
    assert body["data"]["expires_in"] == 300
    assert body["data"]["scope"] == "material:write lkpd:write lkpd:read"

    payload = decode_and_verify_jwt(body["data"]["access_token"])
    assert payload["sub"] == "client:my-client"
    assert payload["scope"] == "material:write lkpd:write lkpd:read"
    assert isinstance(payload.get("jti"), str) and payload["jti"]


def test_oauth_token_invalid_client() -> None:
    client = _build_client()
    response = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "my-client",
            "client_secret": "wrong-secret",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "invalid_client"
    assert body["error"]["details"]["error"] == "invalid_client"


def test_oauth_token_rejects_scope_outside_allowlist() -> None:
    client = _build_client()
    response = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "my-client",
            "client_secret": "my-secret",
            "scope": "material:write admin:all",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "invalid_request"


def test_oauth_token_compat_alias_path() -> None:
    client = _build_client()
    response = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "my-client",
            "client_secret": "my-secret",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "Bearer"
