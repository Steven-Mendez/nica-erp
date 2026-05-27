"""Application settings sourced from environment / .env.local."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor `.env.local` at the repo root regardless of the launching CWD —
# `make api` cd's into `apps/api/` before invoking uvicorn, but the example
# file ships at the repo root and most developers keep their `.env.local`
# alongside it. Walk up: settings.py → bootstrap → src → api → apps → root.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env.local", _REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # `app_env` is REQUIRED — every deployment (local or AWS) explicitly sets
    # this so we never silently fall back to a permissive default. Acceptable
    # values are "local" and "aws".
    app_env: str = Field(...)
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

    # Identity / auth knobs ----------------------------------------------------
    # Local-only HS256 secret for the local JWT issuer. Required when
    # app_env=local; ignored (may be blank) when app_env=aws because Cognito
    # signs tokens with its own keys.
    local_jwt_secret: str = Field(default="")

    # Cognito wiring (populated only in AWS deployments).
    cognito_user_pool_id: str = Field(default="")
    cognito_app_client_id: str = Field(default="")
    cognito_user_pool_domain: str = Field(default="")
    cognito_region: str = Field(default="us-east-1")

    # SES "From" address used in AWS; blank locally where MailHog accepts any.
    ses_from_address: str = Field(default="")

    # SMTP (MailHog) defaults for the operator workstation.
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)

    # Token + verification-code TTLs (seconds).
    jwt_access_ttl_seconds: int = Field(default=3600)
    jwt_refresh_ttl_seconds: int = Field(default=2_592_000)
    signup_code_ttl_seconds: int = Field(default=900)
    password_reset_code_ttl_seconds: int = Field(default=600)

    # Verification throttle: max attempts per rolling window.
    verification_attempts_max: int = Field(default=5)
    verification_attempts_window_seconds: int = Field(default=3600)

    @model_validator(mode="after")
    def _validate_app_env(self) -> Settings:
        if self.app_env == "":
            raise ValueError("APP_ENV must be set explicitly (e.g. 'local' or 'aws')")
        if self.app_env == "local" and self.local_jwt_secret == "":
            raise ValueError("LOCAL_JWT_SECRET must be set when APP_ENV=local")
        return self

    @model_validator(mode="after")
    def _default_cors_for_local(self) -> Settings:
        if self.app_env != "aws" and not self.cors_allowed_origins:
            object.__setattr__(self, "cors_allowed_origins", ["http://localhost:5173"])
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
