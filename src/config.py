import os
import json
from typing import Iterable

from dotenv import load_dotenv
from pydantic import BaseModel


def _parse_int_tuple(raw: str, default: Iterable[int]) -> tuple[int, ...]:
    cleaned = [part.strip() for part in raw.split(",") if part.strip()]
    if not cleaned:
        return tuple(default)

    values: list[int] = []
    for value in cleaned:
        parsed = int(value)
        if parsed < 0:
            raise ValueError("Backoff values must be zero or greater.")
        values.append(parsed)
    return tuple(values)


def _parse_hex_color(raw: str, default: str) -> str:
    value = (raw or "").strip()
    if not value:
        return default

    if not value.startswith("#"):
        value = f"#{value}"

    hex_part = value[1:]
    if len(hex_part) not in (3, 6):
        return default

    try:
        int(hex_part, 16)
    except ValueError:
        return default

    return value.upper()


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_scope_string(raw: str) -> tuple[str, ...]:
    return tuple(part for part in raw.split() if part)


def _parse_required_scopes(
    raw: str, default: dict[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    value = (raw or "").strip()
    if not value:
        return default

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default

    if not isinstance(parsed, dict):
        return default

    out: dict[str, tuple[str, ...]] = {}
    for key, item in parsed.items():
        if not isinstance(key, str):
            continue
        if isinstance(item, str):
            out[key] = _parse_scope_string(item)
            continue
        if isinstance(item, list):
            out[key] = tuple(part for part in item if isinstance(part, str) and part)
            continue

    return out or default


DEFAULT_JWT_REQUIRED_SCOPES: dict[str, tuple[str, ...]] = {
    "/api/material": ("material:write",),
    "/api/mcq": ("material:write",),
    "/api/essay": ("material:write",),
    "/api/summary": ("material:write",),
    "/api/lkpd": ("lkpd:write",),
    "/api/lkpd/files/{file_id}": ("lkpd:read",),
}
DEFAULT_OAUTH_SCOPES: tuple[str, ...] = ("material:write", "lkpd:write", "lkpd:read")


class Settings(BaseModel):
    chroma_persist_dir: str = ".chroma"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_temperature: float = 0.2
    groq_timeout_seconds: int = 30
    mcp_servers_json: str = "{}"
    agent_max_iterations: int = 5
    agent_memory_collection: str = "agent_memory"
    rag_collection_name: str = "material_chunks"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 150
    rag_top_k: int = 8
    rag_fetch_k: int = 24
    rag_mmr_lambda: float = 0.5
    material_max_file_mb: int = 15
    default_mcq_count: int = 10
    default_essay_count: int = 3
    default_summary_max_words: int = 200
    redis_url: str = "redis://localhost:6379/0"
    webhook_callback_timeout_seconds: int = 10
    webhook_callback_max_retries: int = 3
    webhook_callback_backoff_seconds: tuple[int, ...] = (5, 15, 45)
    job_ttl_seconds: int = 86400
    job_queue_key: str = "material_jobs:queue"
    lkpd_default_activity_count: int = 5
    lkpd_min_activity_count: int = 1
    lkpd_max_activity_count: int = 15
    lkpd_job_queue_key: str = "lkpd_jobs:queue"
    lkpd_pdf_dir: str = ".generated/lkpd"
    lkpd_pdf_ttl_seconds: int = 86400
    lkpd_header_logo_path: str = ".assets/lkpd/logo.png"
    lkpd_header_accent_hex: str = "#1F4E79"
    lkpd_header_title_line1: str = "LEMBAR KERJA PESERTA DIDIK (LKPD)"
    lkpd_header_title_line2: str = "SMARTER AI"
    lkpd_header_title_line3: str = ""
    app_public_base_url: str = "http://localhost:8000"
    jwt_enabled: bool = True
    jwt_secret: str = ""
    jwt_issuer: str = "my-backend"
    jwt_audience: str = "rtm-class-ai"
    jwt_clock_skew_seconds: int = 30
    jwt_required_scopes: dict[str, tuple[str, ...]] = DEFAULT_JWT_REQUIRED_SCOPES
    oauth_enabled: bool = False
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_allowed_scopes: tuple[str, ...] = DEFAULT_OAUTH_SCOPES
    oauth_default_scopes: tuple[str, ...] = DEFAULT_OAUTH_SCOPES
    oauth_token_ttl_seconds: int = 300
    oauth_token_rate_limit_window_seconds: int = 60
    oauth_token_rate_limit_per_ip: int = 30
    oauth_token_rate_limit_per_client: int = 30
    jwt_denylist_enabled: bool = True
    jwt_denylist_prefix: str = "auth:denylist:jti:"


def get_settings() -> Settings:
    load_dotenv()
    app_env = os.getenv("APP_ENV", os.getenv("ENV", "")).strip().lower()
    default_jwt_enabled = app_env in {"prod", "production"}
    default_oauth_enabled = app_env in {"prod", "production"}
    jwt_enabled = _parse_bool(os.getenv("JWT_ENABLED"), default=default_jwt_enabled)
    oauth_enabled = _parse_bool(
        os.getenv("OAUTH_ENABLED"),
        default=default_oauth_enabled,
    )
    jwt_secret = os.getenv("JWT_SECRET", "")
    oauth_client_id = os.getenv("OAUTH_CLIENT_ID", "").strip()
    oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET", "")
    oauth_allowed_scopes = _parse_scope_string(
        os.getenv("OAUTH_ALLOWED_SCOPES", " ".join(DEFAULT_OAUTH_SCOPES))
    )
    oauth_default_scopes = _parse_scope_string(
        os.getenv("OAUTH_DEFAULT_SCOPES", " ".join(DEFAULT_OAUTH_SCOPES))
    )

    if not oauth_allowed_scopes:
        oauth_allowed_scopes = DEFAULT_OAUTH_SCOPES
    if not oauth_default_scopes:
        oauth_default_scopes = oauth_allowed_scopes

    if not set(oauth_default_scopes).issubset(set(oauth_allowed_scopes)):
        raise ValueError("OAUTH_DEFAULT_SCOPES must be a subset of OAUTH_ALLOWED_SCOPES.")

    if (jwt_enabled or oauth_enabled) and len(jwt_secret) < 32:
        raise ValueError(
            "JWT_SECRET must be at least 32 characters when JWT or OAuth is enabled."
        )

    if oauth_enabled:
        if not oauth_client_id:
            raise ValueError("OAUTH_CLIENT_ID is required when OAuth is enabled.")
        if not oauth_client_secret:
            raise ValueError("OAUTH_CLIENT_SECRET is required when OAuth is enabled.")

    return Settings(
        chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", ".chroma"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        groq_temperature=float(os.getenv("GROQ_TEMPERATURE", "0.2")),
        groq_timeout_seconds=int(os.getenv("GROQ_TIMEOUT_SECONDS", "30")),
        mcp_servers_json=os.getenv("MCP_SERVERS_JSON", "{}"),
        agent_max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "5")),
        agent_memory_collection=os.getenv("AGENT_MEMORY_COLLECTION", "agent_memory"),
        rag_collection_name=os.getenv("RAG_COLLECTION_NAME", "material_chunks"),
        rag_chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1000")),
        rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "150")),
        rag_top_k=int(os.getenv("RAG_TOP_K", "8")),
        rag_fetch_k=int(os.getenv("RAG_FETCH_K", "24")),
        rag_mmr_lambda=float(os.getenv("RAG_MMR_LAMBDA", "0.5")),
        material_max_file_mb=int(os.getenv("MATERIAL_MAX_FILE_MB", "15")),
        default_mcq_count=int(os.getenv("DEFAULT_MCQ_COUNT", "10")),
        default_essay_count=int(os.getenv("DEFAULT_ESSAY_COUNT", "3")),
        default_summary_max_words=int(os.getenv("DEFAULT_SUMMARY_MAX_WORDS", "200")),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        webhook_callback_timeout_seconds=int(
            os.getenv("WEBHOOK_CALLBACK_TIMEOUT_SECONDS", "10")
        ),
        webhook_callback_max_retries=int(
            os.getenv("WEBHOOK_CALLBACK_MAX_RETRIES", "3")
        ),
        webhook_callback_backoff_seconds=_parse_int_tuple(
            os.getenv("WEBHOOK_CALLBACK_BACKOFF_SECONDS", "5,15,45"),
            default=(5, 15, 45),
        ),
        job_ttl_seconds=int(os.getenv("JOB_TTL_SECONDS", "86400")),
        job_queue_key=os.getenv("JOB_QUEUE_KEY", "material_jobs:queue"),
        lkpd_default_activity_count=int(os.getenv("LKPD_DEFAULT_ACTIVITY_COUNT", "5")),
        lkpd_min_activity_count=int(os.getenv("LKPD_MIN_ACTIVITY_COUNT", "1")),
        lkpd_max_activity_count=int(os.getenv("LKPD_MAX_ACTIVITY_COUNT", "15")),
        lkpd_job_queue_key=os.getenv("LKPD_JOB_QUEUE_KEY", "lkpd_jobs:queue"),
        lkpd_pdf_dir=os.getenv("LKPD_PDF_DIR", ".generated/lkpd"),
        lkpd_pdf_ttl_seconds=int(os.getenv("LKPD_PDF_TTL_SECONDS", "86400")),
        lkpd_header_logo_path=os.getenv("LKPD_HEADER_LOGO_PATH", ".assets/lkpd/logo.png"),
        lkpd_header_accent_hex=_parse_hex_color(
            os.getenv("LKPD_HEADER_ACCENT_HEX", "#1F4E79"),
            default="#1F4E79",
        ),
        lkpd_header_title_line1=os.getenv(
            "LKPD_HEADER_TITLE_LINE1",
            "LEMBAR KERJA PESERTA DIDIK (LKPD)",
        ),
        lkpd_header_title_line2=os.getenv(
            "LKPD_HEADER_TITLE_LINE2",
            "SMARTER AI",
        ),
        lkpd_header_title_line3=os.getenv("LKPD_HEADER_TITLE_LINE3", ""),
        app_public_base_url=os.getenv("APP_PUBLIC_BASE_URL", "http://localhost:8000"),
        jwt_enabled=jwt_enabled,
        jwt_secret=jwt_secret,
        jwt_issuer=os.getenv("JWT_ISSUER", "my-backend"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "rtm-class-ai"),
        jwt_clock_skew_seconds=int(os.getenv("JWT_CLOCK_SKEW_SECONDS", "30")),
        jwt_required_scopes=_parse_required_scopes(
            os.getenv("JWT_REQUIRED_SCOPES", ""),
            default=DEFAULT_JWT_REQUIRED_SCOPES,
        ),
        oauth_enabled=oauth_enabled,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        oauth_allowed_scopes=oauth_allowed_scopes,
        oauth_default_scopes=oauth_default_scopes,
        oauth_token_ttl_seconds=int(os.getenv("OAUTH_TOKEN_TTL_SECONDS", "300")),
        oauth_token_rate_limit_window_seconds=int(
            os.getenv("OAUTH_TOKEN_RATE_LIMIT_WINDOW_SECONDS", "60")
        ),
        oauth_token_rate_limit_per_ip=int(
            os.getenv("OAUTH_TOKEN_RATE_LIMIT_PER_IP", "30")
        ),
        oauth_token_rate_limit_per_client=int(
            os.getenv("OAUTH_TOKEN_RATE_LIMIT_PER_CLIENT", "30")
        ),
        jwt_denylist_enabled=_parse_bool(
            os.getenv("JWT_DENYLIST_ENABLED"),
            default=True,
        ),
        jwt_denylist_prefix=os.getenv("JWT_DENYLIST_PREFIX", "auth:denylist:jti:"),
    )


settings = get_settings()
