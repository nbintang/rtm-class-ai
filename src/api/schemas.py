from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JobAcceptedData(BaseModel):
    job_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"


class OAuthTokenData(BaseModel):
    access_token: str = Field(min_length=1)
    token_type: str = "Bearer"
    expires_in: int = Field(ge=1)
    scope: str
