from langchain_core.documents import Document


def join_context(documents: list[Document], max_chars: int = 6000) -> str:
    parts: list[str] = []
    current_size = 0

    for doc in documents:
        text = doc.page_content.strip()
        if not text:
            continue
        next_size = current_size + len(text)
        if next_size > max_chars:
            break
        parts.append(text)
        current_size = next_size

    return "\n\n".join(parts)
