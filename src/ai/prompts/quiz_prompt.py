def build_quiz_prompt(source_text: str, num_questions: int = 10) -> str:
    return (
        f"Create {num_questions} multiple-choice questions from the text below. "
        "Return concise output with clear answer keys.\n\n"
        f"Source Text:\n{source_text}"
    )

