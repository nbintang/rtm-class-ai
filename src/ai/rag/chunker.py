def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunk = cleaned[start:end]
        chunks.append(chunk)
        if end == len(cleaned):
            break
        start = end - overlap
    return chunks

