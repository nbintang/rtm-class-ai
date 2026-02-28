from src.ai.gateway import get_ai_gateway
from src.ai.prompts.summary_prompt import build_summary_prompt


def generate_summary(source_text: str) -> str:
    gateway = get_ai_gateway()
    return gateway.generate(build_summary_prompt(source_text))

