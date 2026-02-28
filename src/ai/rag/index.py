from __future__ import annotations

from uuid import uuid4

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from src.ai.embeddings import get_embeddings
from src.ai.rag.splitter import get_text_splitter
from src.config import settings


def _build_documents(text: str | None, documents: list[dict] | None) -> list[Document]:
    results: list[Document] = []

    if text:
        results.append(Document(page_content=text, metadata={"source_id": "raw_text"}))

    for doc in documents or []:
        metadata = dict(doc.get("metadata") or {})
        metadata["source_id"] = doc.get("id") or f"doc-{uuid4().hex[:8]}"
        results.append(Document(page_content=doc["text"], metadata=metadata))

    return results


def index_documents(
    collection_name: str,
    text: str | None,
    documents: list[dict] | None,
) -> dict:
    base_docs = _build_documents(text=text, documents=documents)
    chunks = get_text_splitter().split_documents(base_docs)

    for idx, chunk in enumerate(chunks):
        chunk.metadata = {**chunk.metadata, "chunk_id": f"chunk-{idx}"}

    vectorstore = Chroma(
        collection_name=collection_name,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=get_embeddings(),
    )

    ids = [str(uuid4()) for _ in chunks]
    if chunks:
        vectorstore.add_documents(chunks, ids=ids)

    return {
        "collection_name": collection_name,
        "indexed_chunks": len(chunks),
        "document_count": len(base_docs),
        "chunk_ids": [chunk.metadata.get("chunk_id", "") for chunk in chunks],
    }
