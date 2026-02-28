def validate_quiz_content(content: dict, expected_questions: int) -> list[str]:
    warnings: list[str] = []

    questions = content.get("questions", [])
    if len(questions) != expected_questions:
        warnings.append(
            f"Expected {expected_questions} questions but got {len(questions)}."
        )

    for idx, question in enumerate(questions, start=1):
        options = question.get("options", [])
        if len(options) != len(set(options)):
            warnings.append(f"Question {idx}: options are not unique.")

        correct_answer = question.get("correct_answer")
        if correct_answer not in options:
            warnings.append(f"Question {idx}: correct_answer is not in options.")

        if not str(question.get("explanation", "")).strip():
            warnings.append(f"Question {idx}: explanation is empty.")

    return warnings
