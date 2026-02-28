from pydantic import BaseModel, Field

from src.core.constants import DEFAULT_USER_ROLE
from src.modules.users.schemas import UserRead


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str
    role: str = DEFAULT_USER_ROLE


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(UserRead):
    pass

