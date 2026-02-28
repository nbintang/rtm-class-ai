from fastapi import APIRouter

from src.modules.quizzes import service
from src.modules.quizzes.schemas import QuizCreate, QuizRead, QuizResult, QuizSubmission

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.post("/", response_model=QuizRead)
def create_quiz(payload: QuizCreate) -> QuizRead:
    return service.create_quiz(payload)


@router.get("/", response_model=list[QuizRead])
def list_quizzes() -> list[QuizRead]:
    return service.list_quizzes()


@router.get("/{quiz_id}", response_model=QuizRead)
def get_quiz(quiz_id: str) -> QuizRead:
    return service.get_quiz(quiz_id)


@router.post("/{quiz_id}/submit", response_model=QuizResult)
def submit_quiz(quiz_id: str, payload: QuizSubmission) -> QuizResult:
    return service.submit_quiz(quiz_id, payload)

