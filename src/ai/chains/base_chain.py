from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.ai.llm import get_llm


class BaseJsonChain:
    def __init__(self, task_prompt: str) -> None:
        self.parser = JsonOutputParser()
        self.task_prompt = task_prompt
        self.system_prompt = self._load_system_prompt()
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", self.task_prompt),
            ]
        )
        self.chain = self.prompt | get_llm() | self.parser

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = {
            **payload,
            "system_prompt": self.system_prompt,
            "format_instructions": self.parser.get_format_instructions(),
        }
        return self.chain.invoke(inputs)

    @staticmethod
    def _load_system_prompt() -> str:
        path = Path(__file__).resolve().parents[1] / "prompts" / "system.txt"
        return path.read_text(encoding="utf-8").strip()
