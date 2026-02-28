from src.ai.gateway import get_ai_gateway
from src.ai.prompts.remedial_prompt import build_remedial_prompt


def generate_remedial(source_text: str) -> str:
    gateway = get_ai_gateway()
    return gateway.generate(build_remedial_prompt(source_text))

