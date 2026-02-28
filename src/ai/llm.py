from langchain_openai import ChatOpenAI

from src.config import settings


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=temperature,
    )
