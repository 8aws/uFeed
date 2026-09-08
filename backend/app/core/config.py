from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="dev")
    log_level: str = Field(default="info")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ufeed:change-me@db:5432/ufeed",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://ufeed:change-me@db:5432/ufeed",
    )

    # Cache / queues
    redis_url: str = Field(default="redis://cache:6379/0")

    # Auth (used from WS1 onwards)
    jwt_secret: str = Field(default="change-me")
    jwt_access_ttl_min: int = Field(default=15)
    jwt_refresh_ttl_days: int = Field(default=30)

    # i18n
    default_locale: str = Field(default="en")
    supported_locales: tuple[str, ...] = ("en", "es")

    # CORS
    cors_origins: str = Field(default="http://localhost:5173")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
