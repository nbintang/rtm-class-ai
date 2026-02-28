from dataclasses import dataclass
from math import sqrt


@dataclass
class VectorRecord:
    id: str
    text: str
    embedding: list[float]
    metadata: dict


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
    norm_a = sqrt(sum(a * a for a in vector_a))
    norm_b = sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._records: list[VectorRecord] = []

    def add(self, record_id: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        self._records.append(
            VectorRecord(
                id=record_id,
                text=text,
                embedding=embedding,
                metadata=metadata or {},
            )
        )

    def search(self, query_embedding: list[float], top_k: int = 3) -> list[tuple[VectorRecord, float]]:
        scored: list[tuple[VectorRecord, float]] = []
        for record in self._records:
            score = cosine_similarity(query_embedding, record.embedding)
            scored.append((record, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

