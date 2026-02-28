import hashlib

VECTOR_SIZE = 16


def embed_text(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [byte / 255 for byte in digest[:VECTOR_SIZE]]


def embed_many(texts: list[str]) -> list[list[float]]:
    return [embed_text(text) for text in texts]

