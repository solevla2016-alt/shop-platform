"""Application configuration."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    app_name: str = "Green Garden"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1)
    refresh_token_expire_days: int = Field(default=14, ge=1)
    database_url: str | None = None
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "shop"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        base = "postgresql+asyncpg://{}:{}@{}:{}/{}"
        return base.format(
            self.postgres_user,
            self.postgres_password,
            self.postgres_host,
            self.postgres_port,
            self.postgres_db,
        )

    frontend_url: str = "http://localhost:8080"
    resend_api_key: str = ""
    email_from: str = ""
    password_reset_expire_minutes: int = Field(default=15, ge=5, le=60)
    rate_limit_auth_requests: int = Field(default=10, ge=1)
    rate_limit_auth_window_seconds: int = Field(default=60, ge=1)
    admin_email: str | None = None
    admin_phone: str | None = None
    admin_password: str | None = None
    admin_full_name: str | None = None
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:8080,http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        cleaned = [
            item.strip().rstrip("/")
            for item in self.cors_origins.split(",")
            if item.strip()
        ]
        return cleaned

    @field_validator("frontend_url")
    @classmethod
    def normalize_frontend_url(cls, value: str) -> str:
        return value.rstrip("/")

    upload_dir: str = "uploads"
    max_upload_size_mb: int = Field(default=10, ge=1)

    @property
    def uploads_path(self) -> Path:
        return Path(os.path.abspath(self.upload_dir))

    @property
    def categories_upload_dir(self) -> Path:
        return self.uploads_path / "categories"

    @property
    def products_upload_dir(self) -> Path:
        return self.uploads_path / "products"

    def ensure_upload_dirs(self) -> None:
        """Create upload directories if they don't exist."""
        for path in (
            self.categories_upload_dir,
            self.products_upload_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
