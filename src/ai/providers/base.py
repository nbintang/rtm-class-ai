from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        raise NotImplementedError

