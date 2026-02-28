from datetime import datetime, timezone
from uuid import uuid4

from src.core.constants import AVAILABLE_USER_ROLES
from src.core.exceptions import AppError
from src.core.security import hash_password, verify_password
from src.modules.users.schemas import UserCreate, UserRead, UserUpdate

_USERS_BY_ID: dict[str, UserRead] = {}
_USER_ID_BY_EMAIL: dict[str, str] = {}
_PASSWORD_BY_EMAIL: dict[str, str] = {}


def list_users() -> list[UserRead]:
    return sorted(_USERS_BY_ID.values(), key=lambda user: user.created_at, reverse=True)


def get_user_by_id(user_id: str) -> UserRead | None:
    return _USERS_BY_ID.get(user_id)


def get_user_by_email(email: str) -> UserRead | None:
    user_id = _USER_ID_BY_EMAIL.get(email.lower())
    return _USERS_BY_ID.get(user_id) if user_id else None


def create_user(payload: UserCreate) -> UserRead:
    normalized_email = payload.email.lower().strip()
    if normalized_email in _USER_ID_BY_EMAIL:
        raise AppError("Email already registered", status_code=409, code="email_exists")

    role = payload.role.lower().strip()
    if role not in AVAILABLE_USER_ROLES:
        raise AppError("Invalid role", status_code=400, code="invalid_role")

    user_id = str(uuid4())
    user = UserRead(
        id=user_id,
        email=normalized_email,
        full_name=payload.full_name.strip(),
        role=role,
        created_at=datetime.now(timezone.utc),
    )
    _USERS_BY_ID[user_id] = user
    _USER_ID_BY_EMAIL[normalized_email] = user_id
    _PASSWORD_BY_EMAIL[normalized_email] = hash_password(payload.password)
    return user


def update_user(user_id: str, payload: UserUpdate) -> UserRead:
    current = get_user_by_id(user_id)
    if current is None:
        raise AppError("User not found", status_code=404, code="user_not_found")

    role = payload.role or current.role
    if role not in AVAILABLE_USER_ROLES:
        raise AppError("Invalid role", status_code=400, code="invalid_role")

    updated = UserRead(
        id=current.id,
        email=current.email,
        full_name=payload.full_name or current.full_name,
        role=role,
        created_at=current.created_at,
    )
    _USERS_BY_ID[user_id] = updated
    return updated


def verify_user_credentials(email: str, password: str) -> UserRead | None:
    normalized_email = email.lower().strip()
    user = get_user_by_email(normalized_email)
    password_hash = _PASSWORD_BY_EMAIL.get(normalized_email)
    if not user or not password_hash:
        return None
    if not verify_password(password, password_hash):
        return None
    return user

