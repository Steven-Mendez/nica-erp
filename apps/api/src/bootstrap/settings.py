"""Application settings sourced from environment / .env.local."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, model_validator
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

    # In AWS, CloudFront fronts both the SPA and the API at the same origin,
    # so CORS is a no-op and the list is empty. Locally, the Vite dev server
    # (:5173) calls uvicorn (:8000) cross-origin and needs the explicit
    # allow-list. The default is overridable by `CORS_ALLOWED_ORIGINS` in env.
    cors_allowed_origins: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _default_cors_for_local(self) -> Settings:
        if self.app_env != "aws" and not self.cors_allowed_origins:
            object.__setattr__(self, "cors_allowed_origins", ["http://localhost:5173"])
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
