from fastapi import APIRouter, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.exceptions import AppError
from src.modules.auth.schemas import LoginRequest, MeResponse, RegisterRequest, TokenResponse
from src.modules.auth import service
from src.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer(auto_error=False)


@router.post("/register", response_model=UserRead)
def register(payload: RegisterRequest) -> UserRead:
    return service.register(payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    return service.login(payload)


@router.get("/me", response_model=MeResponse)
def me(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> MeResponse:
    if credentials is None:
        raise AppError("Missing bearer token", status_code=401, code="missing_token")
    return MeResponse.model_validate(service.get_current_user(credentials.credentials))

