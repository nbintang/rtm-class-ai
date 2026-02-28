from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import DEFAULT_COLLECTION
from src.schemas.common import SourceRef


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_answer: str
    explanation: str
    difficulty: str | None = None


class QuizContent(BaseModel):
    title: str
    questions: list[QuizQuestion]


class SummaryContent(BaseModel):
    title: str
    overview: str
    key_points: list[str]
    action_items: list[str] = Field(default_factory=list)


class LkpdActivity(BaseModel):
    title: str
    instruction: str
    expected_output: str


class LkpdContent(BaseModel):
    title: str
    objective: str
    activities: list[LkpdActivity]


class RemedialSession(BaseModel):
    session_title: str
    focus: str
    task: str
    success_criteria: str


class RemedialContent(BaseModel):
    title: str
    diagnosis: str
    sessions: list[RemedialSession]


class BaseGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    collection_name: str = DEFAULT_COLLECTION
    use_rag: bool = True
    additional_context: str | None = None


class QuizGenerateRequest(BaseGenerateRequest):
    grade_level: str = "SMP"
    num_questions: int = Field(default=5, ge=1, le=20)


class SummaryGenerateRequest(BaseGenerateRequest):
    max_words: int = Field(default=180, ge=50, le=500)


class LkpdGenerateRequest(BaseGenerateRequest):
    learning_objective: str = "Understand core concept"
    activity_count: int = Field(default=3, ge=1, le=10)


class RemedialGenerateRequest(BaseGenerateRequest):
    weaknesses: list[str] = Field(default_factory=list)
    session_count: int = Field(default=3, ge=1, le=10)


class QuizGenerateResponse(BaseModel):
    content: QuizContent
    sources: list[SourceRef]
    warnings: list[str]


class SummaryGenerateResponse(BaseModel):
    content: SummaryContent
    sources: list[SourceRef]
    warnings: list[str]


class LkpdGenerateResponse(BaseModel):
    content: LkpdContent
    sources: list[SourceRef]
    warnings: list[str]


class RemedialGenerateResponse(BaseModel):
    content: RemedialContent
    sources: list[SourceRef]
    warnings: list[str]
