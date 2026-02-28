def normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def truncate(text: str, max_chars: int = 200) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."

