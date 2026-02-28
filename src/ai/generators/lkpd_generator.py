from src.ai.gateway import get_ai_gateway
from src.ai.prompts.lkpd_prompt import build_lkpd_prompt


def generate_lkpd(source_text: str) -> str:
    gateway = get_ai_gateway()
    return gateway.generate(build_lkpd_prompt(source_text))

