from __future__ import annotations

from typing import Any

from src.agent.infra.model_provider import get_groq_chat_model


def create_generation_agent(*, tools: list[Any]):
    try:
        from langchain.agents import create_agent
    except ImportError as exc:
        raise RuntimeError(
            "langchain is not installed. Install dependencies before using /api/material."
        ) from exc

    return create_agent(
        model=get_groq_chat_model(),
        tools=tools,
    )

