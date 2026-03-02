from __future__ import annotations

from typing import Any

from src.agent.infra.memory_store import LongTermMemoryStore


def build_internal_tools(*, memory_store: LongTermMemoryStore, user_id: str) -> list[Any]:
    try:
        from langchain_core.tools import tool
    except ImportError as exc:
        raise RuntimeError(
            "langchain-core is not installed. Install dependencies before using /api/material."
        ) from exc

    @tool
    def remember_user_fact(fact: str, memory_type: str = "general") -> str:
        """Save a durable user fact into long-term memory."""
        memory_id = memory_store.remember_fact(
            user_id=user_id,
            fact=fact,
            memory_type=memory_type,
        )
        if not memory_id:
            return "No memory saved because the fact was empty."
        return f"Saved memory with id {memory_id}."

    @tool
    def recall_user_facts(query: str = "", limit: int = 5) -> str:
        """Recall previously saved user facts for personalization."""
        docs = memory_store.recall_user_facts(
            user_id=user_id,
            query=query,
            limit=limit,
        )
        if not docs:
            return "No memories found for this user."

        lines: list[str] = []
        for idx, doc in enumerate(docs, start=1):
            metadata = doc.metadata or {}
            memory_type = metadata.get("memory_type", "general")
            created_at = metadata.get("created_at", "unknown")
            lines.append(
                f"{idx}. [{memory_type}] ({created_at}) {doc.page_content}"
            )
        return "\n".join(lines)

    return [remember_user_fact, recall_user_facts]

