from fastapi import FastAPI

from src.api.routes import router
from src.core.constants import APP_NAME, APP_VERSION
from src.core.exceptions import register_exception_handlers
from src.core.logging import configure_logging

configure_logging()

app = FastAPI(title=APP_NAME, version=APP_VERSION)
register_exception_handlers(app)
app.include_router(router)
