from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from src.config import settings


def _normalize_chunks(chunks: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for chunk in chunks:
        clean = " ".join(chunk.split())
        if clean:
            normalized.append(clean)
    return normalized


def split_material_text(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be zero or greater.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    clean = " ".join(text.split())
    if not clean:
        return []

    if len(clean) <= chunk_size:
        return [clean]

    step = chunk_size - chunk_overlap
    chunks: list[str] = []
    for start in range(0, len(clean), step):
        segment = clean[start : start + chunk_size]
        if not segment.strip():
            continue
        chunks.append(segment)
        if start + chunk_size >= len(clean):
            break
    return _normalize_chunks(chunks)


def _to_float_list(values: object) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()

    if isinstance(values, (list, tuple)):
        converted: list[float] = []
        for item in values:
            if hasattr(item, "item"):
                item = item.item()
            converted.append(float(item))
        return converted

    if hasattr(values, "item"):
        values = values.item()
    return [float(values)]


def _to_float_vectors(values: object) -> list[list[float]]:
    if hasattr(values, "tolist"):
        values = values.tolist()

    if not isinstance(values, (list, tuple)):
        return [_to_float_list(values)]
    if not values:
        return []

    first = values[0]
    if isinstance(first, (list, tuple)) or hasattr(first, "tolist"):
        return [_to_float_list(vector) for vector in values]
    return [_to_float_list(values)]


def _short_error_message(exc: Exception, *, max_chars: int = 260) -> str:
    compact = " ".join(str(exc).split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def _build_embeddings() -> tuple[Embeddings, str | None]:
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        class ChromaDefaultEmbeddings(Embeddings):
            def __init__(self) -> None:
                self._fn = DefaultEmbeddingFunction()

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                vectors = self._fn(texts)
                return _to_float_vectors(vectors)

            def embed_query(self, text: str) -> list[float]:
                vector = self._fn([text])[0]
                return _to_float_list(vector)

        return ChromaDefaultEmbeddings(), None
    except Exception as exc:
        return (
            DeterministicFakeEmbedding(size=256),
            f"RAG embedding fallback mode: {exc}",
        )


class MaterialRAGStore:
    def __init__(self) -> None:
        self._warning: str | None = None
        self._fallback_docs: list[Document] = []
        self._vectorstore = None
        self._embeddings, emb_warning = _build_embeddings()
        if emb_warning:
            self._warning = emb_warning

        try:
            from langchain_chroma import Chroma

            self._vectorstore = Chroma(
                collection_name=settings.rag_collection_name,
                persist_directory=settings.chroma_persist_dir,
                embedding_function=self._embeddings,
            )
        except Exception as exc:
            warning = f"Material RAG vectorstore fallback mode: {exc}"
            self._warning = f"{self._warning}; {warning}" if self._warning else warning

    @property
    def init_warning(self) -> str | None:
        return self._warning

    def index_material(
        self,
        *,
        user_id: str,
        document_id: str,
        filename: str,
        file_type: str,
        text: str,
    ) -> tuple[int, list[str]]:
        warnings: list[str] = []

        chunks = split_material_text(
            text,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        if not chunks:
            raise ValueError("No chunks produced for RAG indexing.")

        now = datetime.now(UTC).isoformat()
        docs: list[Document] = []
        doc_ids: list[str] = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{document_id}:chunk:{idx}"
            metadata = {
                "chunk_id": chunk_id,
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "file_type": file_type,
                "chunk_index": idx,
                "uploaded_at": now,
                "source": "uploaded_material_chunk",
            }
            docs.append(Document(page_content=chunk, metadata=metadata))
            doc_ids.append(chunk_id)

        self._fallback_docs.extend(docs)

        if self._vectorstore is not None:
            try:
                self._vectorstore.add_documents(docs, ids=doc_ids)
            except Exception as exc:
                warnings.append(
                    f"RAG indexing fallback to memory: {_short_error_message(exc)}"
                )
        else:
            warnings.append("RAG vectorstore unavailable; using in-memory fallback.")

        return len(docs), warnings

    def retrieve_for_generation(
        self,
        *,
        user_id: str,
        document_id: str,
        queries: list[str],
    ) -> tuple[list[Document], list[str]]:
        warnings: list[str] = []
        if not queries:
            return [], warnings

        where = {"user_id": user_id, "document_id": document_id}

        if self._vectorstore is None:
            docs = self._fallback_retrieve(
                user_id=user_id,
                document_id=document_id,
                queries=queries,
            )
            if docs:
                return docs, warnings
            warnings.append("RAG retrieval returned no chunks from fallback memory.")
            return [], warnings

        try:
            collected: list[Document] = []
            for query in queries:
                docs = self._vectorstore.max_marginal_relevance_search(
                    query=query,
                    k=settings.rag_top_k,
                    fetch_k=settings.rag_fetch_k,
                    lambda_mult=settings.rag_mmr_lambda,
                    filter=where,
                )
                collected.extend(docs)

            deduped = self._dedupe_docs(collected)
            if deduped:
                return deduped, warnings

            warnings.append("RAG retrieval returned no chunks.")
            return [], warnings
        except Exception as exc:
            warnings.append(
                f"RAG retrieval failed; fallback to memory: {_short_error_message(exc)}"
            )
            docs = self._fallback_retrieve(
                user_id=user_id,
                document_id=document_id,
                queries=queries,
            )
            return docs, warnings

    def new_document_id(self) -> str:
        return f"doc-{uuid4().hex}"

    @staticmethod
    def _dedupe_docs(docs: list[Document]) -> list[Document]:
        deduped: list[Document] = []
        seen: set[str] = set()
        for doc in docs:
            metadata = doc.metadata or {}
            chunk_id = str(metadata.get("chunk_id") or "")
            key = chunk_id if chunk_id else doc.page_content[:128]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    def _fallback_retrieve(
        self,
        *,
        user_id: str,
        document_id: str,
        queries: list[str],
    ) -> list[Document]:
        candidates = [
            doc
            for doc in self._fallback_docs
            if (doc.metadata or {}).get("user_id") == user_id
            and (doc.metadata or {}).get("document_id") == document_id
        ]
        if not candidates:
            return []

        query_terms = {
            term.lower()
            for term in " ".join(queries).split()
            if len(term.strip()) >= 3
        }

        scored: list[tuple[int, Document]] = []
        for doc in candidates:
            text = doc.page_content.lower()
            score = sum(1 for term in query_terms if term in text)
            scored.append((score, doc))

        scored.sort(
            key=lambda item: (
                item[0],
                -int((item[1].metadata or {}).get("chunk_index", 0)),
            ),
            reverse=True,
        )
        limit = max(1, settings.rag_top_k)
        return [item[1] for item in scored[:limit]]
