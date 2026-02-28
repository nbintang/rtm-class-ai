def build_summary_prompt(source_text: str) -> str:
    return (
        "Summarize the source text for high school students. "
        "Highlight key concepts and practical examples.\n\n"
        f"Source Text:\n{source_text}"
    )

