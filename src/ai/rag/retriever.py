from dataclasses import dataclass

from src.ai.rag.chunker import chunk_text
from src.ai.rag.embedder import embed_text
from src.ai.rag.vector_store import InMemoryVectorStore


@dataclass
class RetrievalResult:
    id: str
    text: str
    score: float
    metadata: dict


class Retriever:
    def __init__(self, store: InMemoryVectorStore | None = None) -> None:
        self.store = store or InMemoryVectorStore()

    def add_document(self, document_id: str, text: str, metadata: dict | None = None) -> None:
        for index, chunk in enumerate(chunk_text(text)):
            chunk_id = f"{document_id}:{index}"
            self.store.add(
                record_id=chunk_id,
                text=chunk,
                embedding=embed_text(chunk),
                metadata=metadata or {},
            )

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        query_embedding = embed_text(query)
        matches = self.store.search(query_embedding=query_embedding, top_k=top_k)
        return [
            RetrievalResult(
                id=record.id,
                text=record.text,
                score=score,
                metadata=record.metadata,
            )
            for record, score in matches
        ]

