from src.config import get_settings
from src.core.exceptions import AppError
from src.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from src.modules.users.schemas import UserCreate, UserRead
from src.modules.users import service as users_service
from src.utils.token import create_access_token, decode_access_token

settings = get_settings()


def register(payload: RegisterRequest) -> UserRead:
    return users_service.create_user(
        UserCreate(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
        )
    )


def login(payload: LoginRequest) -> TokenResponse:
    user = users_service.verify_user_credentials(payload.email, payload.password)
    if not user:
        raise AppError("Invalid email or password", status_code=401, code="invalid_credentials")

    expires_seconds = settings.token_expire_minutes * 60
    token = create_access_token(
        payload={"sub": user.id, "email": user.email, "role": user.role},
        secret=settings.jwt_secret,
        expires_in_seconds=expires_seconds,
    )
    return TokenResponse(access_token=token, expires_in=expires_seconds)


def get_current_user(token: str) -> UserRead:
    payload = decode_access_token(token=token, secret=settings.jwt_secret)
    user_id = payload.get("sub")
    if not user_id:
        raise AppError("Invalid token payload", status_code=401, code="invalid_token")

    user = users_service.get_user_by_id(user_id)
    if not user:
        raise AppError("User not found", status_code=404, code="user_not_found")
    return user

