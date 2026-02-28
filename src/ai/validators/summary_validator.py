def validate_summary_content(
    content: dict,
    max_words: int,
    require_sections: bool = True,
) -> list[str]:
    warnings: list[str] = []

    overview = str(content.get("overview", "")).strip()
    if not overview:
        warnings.append("Summary overview is empty.")

    if require_sections:
        sections = ["title", "overview", "key_points"]
        for section in sections:
            if section not in content:
                warnings.append(f"Missing required section: {section}.")

    word_count = len(overview.split())
    if word_count > max_words:
        warnings.append(f"Overview exceeds max_words ({word_count} > {max_words}).")

    return warnings
