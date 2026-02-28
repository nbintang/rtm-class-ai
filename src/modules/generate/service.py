from src.ai.generators.lkpd_generator import generate_lkpd
from src.ai.generators.quiz_generator import generate_quiz
from src.ai.generators.remedial_generator import generate_remedial
from src.ai.generators.summary_generator import generate_summary
from src.core.exceptions import AppError
from src.modules.generate.schemas import GenerateRequest, GenerateResponse


def generate_content(payload: GenerateRequest) -> GenerateResponse:
    kind = payload.kind.lower().strip()

    if kind == "quiz":
        content = generate_quiz(payload.text)
    elif kind == "summary":
        content = generate_summary(payload.text)
    elif kind == "lkpd":
        content = generate_lkpd(payload.text)
    elif kind == "remedial":
        content = generate_remedial(payload.text)
    else:
        raise AppError("Unsupported generation kind", status_code=400, code="unsupported_generation_kind")

    return GenerateResponse(kind=kind, content=content)

