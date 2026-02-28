from fastapi import FastAPI

from src.config import get_settings
from src.core.exceptions import AppError, app_error_handler
from src.core.logging import configure_logging
from src.modules.auth.routes import router as auth_router
from src.modules.generate.routes import router as generate_router
from src.modules.materials.routes import router as materials_router
from src.modules.quizzes.routes import router as quizzes_router
from src.modules.users.routes import router as users_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
    )

    app.add_exception_handler(AppError, app_error_handler)

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(users_router, prefix=settings.api_prefix)
    app.include_router(materials_router, prefix=settings.api_prefix)
    app.include_router(generate_router, prefix=settings.api_prefix)
    app.include_router(quizzes_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["System"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
