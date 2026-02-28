from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    app_env: str
    api_prefix: str
    log_level: str
    database_url: str
    ai_provider: str
    ai_model: str
    openai_api_key: str
    jwt_secret: str
    token_expire_minutes: int
    storage_backend: str
    local_storage_path: str
    aws_region: str
    aws_s3_bucket: str
    aws_access_key_id: str
    aws_secret_access_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "RTM Class AI"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            app_env=os.getenv("APP_ENV", "development"),
            api_prefix=os.getenv("API_PREFIX", "/api/v1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./rtm_class_ai.db"),
            ai_provider=os.getenv("AI_PROVIDER", "openai"),
            ai_model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            jwt_secret=os.getenv("JWT_SECRET", "change-this-secret"),
            token_expire_minutes=int(os.getenv("TOKEN_EXPIRE_MINUTES", "120")),
            storage_backend=os.getenv("STORAGE_BACKEND", "local"),
            local_storage_path=os.getenv("LOCAL_STORAGE_PATH", "./data/storage"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_s3_bucket=os.getenv("AWS_S3_BUCKET", ""),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
