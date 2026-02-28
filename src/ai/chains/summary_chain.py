from src.ai.chains.base_chain import BaseJsonChain
from src.ai.prompts.summary_prompt import SUMMARY_PROMPT


class SummaryChain(BaseJsonChain):
    def __init__(self) -> None:
        super().__init__(task_prompt=SUMMARY_PROMPT)
