import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    chroma_persist_dir: str = ".chroma"
    top_k: int = 4
    max_chunk_size: int = 800
    chunk_overlap: int = 120


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_embed_model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", ".chroma"),
        top_k=int(os.getenv("TOP_K", "4")),
        max_chunk_size=int(os.getenv("MAX_CHUNK_SIZE", "800")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
    )


settings = get_settings()
