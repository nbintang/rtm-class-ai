from __future__ import annotations

import os

from src.config import settings
from langchain_groq import ChatGroq as _ChatGroq


def get_groq_chat_model():
    if _ChatGroq is None:
        raise RuntimeError(
            "langchain-groq is not installed. Install dependencies before using /api/material."
        )

    if settings.groq_api_key:
        os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)

    return _ChatGroq(
        model=settings.groq_model,
        temperature=settings.groq_temperature,
        timeout=settings.groq_timeout_seconds,
        max_retries=2,
    )
