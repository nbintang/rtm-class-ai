from pydantic import BaseModel, Field

from src.agent.types.quiz import EssayQuiz, McqQuiz
from src.agent.types.summary import SummaryContent


class McqInsertArgs(BaseModel):
    job_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    requested_by_id: str = Field(min_length=1)
    mcq_quiz: McqQuiz


class EssayInsertArgs(BaseModel):
    job_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    requested_by_id: str = Field(min_length=1)
    essay_quiz: EssayQuiz


class SummaryInsertArgs(BaseModel):
    job_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    requested_by_id: str = Field(min_length=1)
    summary: SummaryContent

