from src.ai.chains.base_chain import BaseJsonChain
from src.ai.prompts.quiz_prompt import QUIZ_PROMPT


class QuizChain(BaseJsonChain):
    def __init__(self) -> None:
        super().__init__(task_prompt=QUIZ_PROMPT)
