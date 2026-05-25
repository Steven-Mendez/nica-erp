"""Application settings sourced from environment / .env.local."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="local")
    version: str = Field(default="0.1.0")
    git_sha: str = Field(default_factory=lambda: os.environ.get("GIT_SHA", "unknown"))

    database_url: str = Field(
        default="postgresql+asyncpg://nica_erp:nica_erp@localhost:5432/nica_erp",
    )
    alembic_database_url: str = Field(
        default="postgresql+psycopg://nica_erp:nica_erp@localhost:5432/nica_erp",
    )

    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
