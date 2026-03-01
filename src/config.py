import os
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
    app_public_base_url: str = "http://localhost:8000"


def get_settings() -> Settings:
    load_dotenv()
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
        app_public_base_url=os.getenv("APP_PUBLIC_BASE_URL", "http://localhost:8000"),
    )


settings = get_settings()
