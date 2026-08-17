"""Application settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Shop API"
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    rate_limit_auth_requests: int = 10
    rate_limit_auth_window_seconds: int = 60

    log_level: str = "INFO"

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "shop"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: Optional[str] = None

    admin_email: Optional[str] = None
    admin_phone: Optional[str] = None
    admin_password: Optional[str] = None
    admin_full_name: Optional[str] = None

    @property
    def async_database_url(self) -> str:
        """Return SQLAlchemy async database URL."""
        if self.database_url:
            url = self.database_url

            if url.startswith("postgresql+asyncpg://"):
                return url

            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)

            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://", 1)

            return url

        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
