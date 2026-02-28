from datetime import datetime, timezone
from uuid import uuid4

from src.ai.validators.quiz_validator import validate_quiz_questions
from src.core.exceptions import AppError
from src.modules.quizzes.scoring import calculate_score
from src.modules.quizzes.schemas import QuizCreate, QuizRead, QuizResult, QuizSubmission

_QUIZZES: dict[str, QuizRead] = {}


def create_quiz(payload: QuizCreate) -> QuizRead:
    if not validate_quiz_questions(payload.questions):
        raise AppError("Invalid quiz payload", status_code=400, code="invalid_quiz_payload")

    quiz = QuizRead(
        id=str(uuid4()),
        title=payload.title.strip(),
        questions=payload.questions,
        created_at=datetime.now(timezone.utc),
    )
    _QUIZZES[quiz.id] = quiz
    return quiz


def list_quizzes() -> list[QuizRead]:
    return sorted(_QUIZZES.values(), key=lambda item: item.created_at, reverse=True)


def get_quiz(quiz_id: str) -> QuizRead:
    quiz = _QUIZZES.get(quiz_id)
    if quiz is None:
        raise AppError("Quiz not found", status_code=404, code="quiz_not_found")
    return quiz


def submit_quiz(quiz_id: str, payload: QuizSubmission) -> QuizResult:
    quiz = get_quiz(quiz_id)
    score, correct, total = calculate_score(quiz.questions, payload.answers)
    feedback = "Great work." if score >= 80 else "Review the material and try again."
    return QuizResult(
        quiz_id=quiz_id,
        score=score,
        correct=correct,
        total=total,
        feedback=feedback,
    )

