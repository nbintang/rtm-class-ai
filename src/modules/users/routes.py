from fastapi import APIRouter

from src.modules.users import service
from src.modules.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserRead])
def list_users() -> list[UserRead]:
    return service.list_users()


@router.post("/", response_model=UserRead)
def create_user(payload: UserCreate) -> UserRead:
    return service.create_user(payload)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: str) -> UserRead:
    user = service.get_user_by_id(user_id)
    if user is None:
        from src.core.exceptions import AppError

        raise AppError("User not found", status_code=404, code="user_not_found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: str, payload: UserUpdate) -> UserRead:
    return service.update_user(user_id, payload)

