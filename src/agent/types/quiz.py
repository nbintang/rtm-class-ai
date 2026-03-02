from pydantic import BaseModel, Field, model_validator


class McqQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[str]
    correct_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_options(self) -> "McqQuestion":
        if len(self.options) != 4:
            raise ValueError("MCQ options must contain exactly 4 items.")
        if len(set(self.options)) != len(self.options):
            raise ValueError("MCQ options must be unique.")
        if self.correct_answer not in self.options:
            raise ValueError("MCQ correct_answer must match one option.")
        return self


class McqQuiz(BaseModel):
    questions: list[McqQuestion]


class EssayQuestion(BaseModel):
    question: str = Field(min_length=1)
    expected_points: str = Field(min_length=1)


class EssayQuiz(BaseModel):
    questions: list[EssayQuestion]

