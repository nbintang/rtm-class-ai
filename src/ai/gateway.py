import logging
from pathlib import Path

from src.ai.providers.base import AIProvider
from src.ai.providers.openai_provider import OpenAIProvider
from src.config import get_settings

LOGGER = logging.getLogger(__name__)


class EchoProvider(AIProvider):
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        _ = temperature
        if system_prompt:
            return f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{prompt}"
        return prompt


def _load_default_system_prompt() -> str:
    path = Path(__file__).resolve().parent / "prompts" / "system.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "You are an assistant for educational content generation."


class AIGateway:
    def __init__(self, provider: AIProvider, default_system_prompt: str | None = None) -> None:
        self.provider = provider
        self.default_system_prompt = default_system_prompt or _load_default_system_prompt()

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        active_system_prompt = system_prompt or self.default_system_prompt
        return self.provider.generate(
            prompt=prompt,
            system_prompt=active_system_prompt,
            temperature=temperature,
        )

    @classmethod
    def from_settings(cls) -> "AIGateway":
        settings = get_settings()
        provider_name = settings.ai_provider.lower().strip()

        if provider_name == "openai" and settings.openai_api_key:
            provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.ai_model,
            )
        else:
            LOGGER.warning("Using EchoProvider (set OPENAI_API_KEY for OpenAI integration).")
            provider = EchoProvider()

        return cls(provider=provider)


_gateway: AIGateway | None = None


def get_ai_gateway() -> AIGateway:
    global _gateway
    if _gateway is None:
        _gateway = AIGateway.from_settings()
    return _gateway

