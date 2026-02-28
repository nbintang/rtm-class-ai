from src.ai.gateway import get_ai_gateway
from src.ai.prompts.quiz_prompt import build_quiz_prompt


def generate_quiz(source_text: str) -> str:
    gateway = get_ai_gateway()
    return gateway.generate(build_quiz_prompt(source_text))

