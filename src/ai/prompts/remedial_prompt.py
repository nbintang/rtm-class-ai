def build_remedial_prompt(source_text: str) -> str:
    return (
        "Create remedial learning material from the source text for students "
        "who need simpler explanations and guided steps.\n\n"
        f"Source Text:\n{source_text}"
    )

