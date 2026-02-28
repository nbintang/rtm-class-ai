from fastapi import APIRouter

from src.modules.generate.schemas import GenerateRequest, GenerateResponse
from src.modules.generate.service import generate_content

router = APIRouter(prefix="/generate", tags=["Generate"])


@router.post("/", response_model=GenerateResponse)
def generate(payload: GenerateRequest) -> GenerateResponse:
    return generate_content(payload)

