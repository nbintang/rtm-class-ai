from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document

from src.config import settings


class LongTermMemoryStore:
    def __init__(self) -> None:
        self._fallback: dict[str, list[Document]] = defaultdict(list)
        self._init_warning: str | None = None
        self._vectorstore = None

        try:
            from langchain_chroma import Chroma

            self._vectorstore = Chroma(
                collection_name=settings.agent_memory_collection,
                persist_directory=settings.chroma_persist_dir,
            )
        except Exception as exc:
            self._init_warning = (
                f"Long-term vector memory fallback mode: {exc}"
            )

    @property
    def init_warning(self) -> str | None:
        return self._init_warning

    def remember_fact(
        self,
        *,
        user_id: str,
        fact: str,
        memory_type: str = "general",
        source: str = "agent_memory",
        extra_metadata: dict[str, Any] | None = None,
    ) -> str:
        cleaned = fact.strip()
        if not cleaned:
            return ""

        memory_id = f"mem-{uuid4().hex}"
        metadata: dict[str, Any] = {
            "memory_id": memory_id,
            "user_id": user_id,
            "memory_type": memory_type,
            "created_at": datetime.now(UTC).isoformat(),
            "source": source,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        doc = Document(page_content=cleaned, metadata=metadata)
        self._fallback[user_id].append(doc)

        if self._vectorstore is not None:
            try:
                self._vectorstore.add_documents([doc], ids=[memory_id])
            except Exception:
                # Keep service available even if vector persistence fails.
                pass

        return memory_id

    def recall_user_facts(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[Document]:
        safe_limit = max(1, min(limit, 20))
        where = {"user_id": user_id}

        if self._vectorstore is not None and query.strip():
            try:
                docs = self._vectorstore.similarity_search(
                    query.strip(),
                    k=safe_limit,
                    filter=where,
                )
                if docs:
                    return docs
            except Exception:
                pass

        if self._vectorstore is not None:
            try:
                payload = self._vectorstore.get(
                    where=where,
                    limit=safe_limit,
                    include=["documents", "metadatas"],
                )
                documents = payload.get("documents", [])
                metadatas = payload.get("metadatas", [])
                docs: list[Document] = []
                for text, metadata in zip(documents, metadatas):
                    if text:
                        docs.append(
                            Document(
                                page_content=text,
                                metadata=dict(metadata or {}),
                            )
                        )
                if docs:
                    return docs
            except Exception:
                pass

        return self._fallback.get(user_id, [])[-safe_limit:]
