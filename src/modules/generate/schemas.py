from pydantic import BaseModel


class GenerateRequest(BaseModel):
    kind: str
    text: str


class GenerateResponse(BaseModel):
    kind: str
    content: str

