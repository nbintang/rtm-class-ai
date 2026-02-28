def rough_token_count(text: str) -> int:
    # Quick approximation for planning context windows.
    return max(1, len(text) // 4)
