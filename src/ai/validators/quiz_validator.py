from collections.abc import Sequence

from src.modules.quizzes.schemas import QuizQuestion


def validate_quiz_questions(questions: Sequence[QuizQuestion]) -> bool:
    if not questions:
        return False
    for item in questions:
        if not item.question.strip():
            return False
        if not item.answer.strip():
            return False
    return True

