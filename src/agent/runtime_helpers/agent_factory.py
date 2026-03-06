from __future__ import annotations

from typing import Any

from src.agent.infra.model_provider import get_groq_chat_model
from langchain.agents import create_agent as _create_agent


def create_generation_agent(*, tools: list[Any]):
    if _create_agent is None:
        raise RuntimeError(
            "langchain is not installed. Install dependencies before using /api/material."
        )

    return _create_agent(
        model=get_groq_chat_model(),
        tools=tools,
    )
