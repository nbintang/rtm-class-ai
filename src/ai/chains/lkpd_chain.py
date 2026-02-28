from src.ai.chains.base_chain import BaseJsonChain
from src.ai.prompts.lkpd_prompt import LKPD_PROMPT


class LkpdChain(BaseJsonChain):
    def __init__(self) -> None:
        super().__init__(task_prompt=LKPD_PROMPT)
