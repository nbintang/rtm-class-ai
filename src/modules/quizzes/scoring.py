from collections.abc import Sequence

from src.modules.quizzes.schemas import QuizQuestion


def calculate_score(questions: Sequence[QuizQuestion], answers: Sequence[str]) -> tuple[float, int, int]:
    total = len(questions)
    if total == 0:
        return 0.0, 0, 0

    correct = 0
    for index, question in enumerate(questions):
        provided = answers[index].strip().lower() if index < len(answers) else ""
        expected = question.answer.strip().lower()
        if provided == expected:
            correct += 1

    score = round((correct / total) * 100, 2)
    return score, correct, total

