from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import load_dotenv

# load .env from project root (current working dir) if exists
load_dotenv()

def build_token(
    *,
    secret: str,
    issuer: str,
    audience: str,
    subject: str,
    scope: str,
    ttl_seconds: int,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    if scope:
        payload["scope"] = scope
    return jwt.encode(payload, secret, algorithm="HS256")


def _parse_kv(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        out[key] = value
    return out


def _resolve_token(args: argparse.Namespace) -> str:
    if args.token:
        return args.token
    return build_token(
        secret=args.secret,
        issuer=args.issuer,
        audience=args.audience,
        subject=args.subject,
        scope=args.scope,
        ttl_seconds=args.ttl,
    )


def _cmd_token(args: argparse.Namespace) -> int:
    token = build_token(
        secret=args.secret,
        issuer=args.issuer,
        audience=args.audience,
        subject=args.subject,
        scope=args.scope,
        ttl_seconds=args.ttl,
    )
    print(token)
    return 0


def _cmd_call(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    headers = {"Authorization": f"Bearer {token}"}

    method = args.method.upper()
    data = _parse_kv(args.form)
    files_arg = _parse_kv(args.file)

    opened_files: list[Any] = []
    files: dict[str, Any] = {}
    try:
        for field, path_value in files_arg.items():
            path = Path(path_value)
            file_handle = path.open("rb")
            opened_files.append(file_handle)
            files[field] = (path.name, file_handle)

        with httpx.Client(timeout=args.timeout) as client:
            response = client.request(
                method=method,
                url=args.url,
                headers=headers,
                data=data or None,
                files=files or None,
            )
    finally:
        for fh in opened_files:
            fh.close()

    print(f"HTTP {response.status_code}")
    print(response.text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    env_secret = os.getenv("JWT_SECRET", "")
    env_issuer = os.getenv("JWT_ISSUER", "my-backend")
    env_audience = os.getenv("JWT_AUDIENCE", "rtm-class-ai")
    env_subject = os.getenv("JWT_SUBJECT", "service:backend")
    env_scope = os.getenv(
        "JWT_SCOPE", "material:write lkpd:write lkpd:read"
    )

    parser = argparse.ArgumentParser(
        description="Generate and test JWT for rtm-class-ai service auth."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    token_parser = subparsers.add_parser("token", help="Generate and print JWT.")
    token_parser.add_argument("--secret", default=env_secret, required=not bool(env_secret))
    token_parser.add_argument("--issuer", default=env_issuer)
    token_parser.add_argument("--audience", default=env_audience)
    token_parser.add_argument("--subject", default=env_subject)
    token_parser.add_argument("--scope", default=env_scope)
    token_parser.add_argument("--ttl", type=int, default=300)
    token_parser.set_defaults(func=_cmd_token)

    call_parser = subparsers.add_parser("call", help="Call endpoint with Bearer JWT.")
    call_parser.add_argument("--url", required=True)
    call_parser.add_argument("--method", default="GET")
    call_parser.add_argument("--token", default="")
    call_parser.add_argument("--secret", default=env_secret, required=not bool(env_secret))
    call_parser.add_argument("--issuer", default=env_issuer)
    call_parser.add_argument("--audience", default=env_audience)
    call_parser.add_argument("--subject", default=env_subject)
    call_parser.add_argument("--scope", default=env_scope)
    call_parser.add_argument("--ttl", type=int, default=300)
    call_parser.add_argument("--form", action="append", default=[], help="key=value")
    call_parser.add_argument("--file", action="append", default=[], help="field=path")
    call_parser.add_argument("--timeout", type=float, default=30)
    call_parser.set_defaults(func=_cmd_call)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
