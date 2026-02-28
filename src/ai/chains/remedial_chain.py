from src.ai.chains.base_chain import BaseJsonChain
from src.ai.prompts.remedial_prompt import REMEDIAL_PROMPT


class RemedialChain(BaseJsonChain):
    def __init__(self) -> None:
        super().__init__(task_prompt=REMEDIAL_PROMPT)
