def validate_summary(summary: str, min_words: int = 20) -> bool:
    words = [word for word in summary.split() if word.strip()]
    return len(words) >= min_words

