from datetime import datetime

from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    question: str = Field(min_length=1)
    choices: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1)


class QuizCreate(BaseModel):
    title: str = Field(min_length=1)
    questions: list[QuizQuestion] = Field(min_length=1)


class QuizRead(BaseModel):
    id: str
    title: str
    questions: list[QuizQuestion]
    created_at: datetime


class QuizSubmission(BaseModel):
    answers: list[str] = Field(default_factory=list)


class QuizResult(BaseModel):
    quiz_id: str
    score: float
    correct: int
    total: int
    feedback: str

