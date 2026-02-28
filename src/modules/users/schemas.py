from datetime import datetime

from pydantic import BaseModel, Field

from src.core.constants import DEFAULT_USER_ROLE


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str
    role: str = DEFAULT_USER_ROLE


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None


class UserRead(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

