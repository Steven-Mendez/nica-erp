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

    # Tenant + RBAC knobs. Invitation tokens default to a 7-day window; the
    # permission cache holds the role-to-permissions mapping for 60 s per
    # process.
    invitation_token_ttl_seconds: int = Field(default=604_800)
    permission_cache_ttl_seconds: int = Field(default=60)

    # Login-attempt throttle (sliding window). Identifier: 5 failures /
    # 15 min before the operator's email is locked out. IP: 20 failures
    # / 15 min before the source IP is locked out regardless of which
    # identifiers it targeted. The two windows are independent and the
    # IP counter is NOT cleared by a successful login (a credential-
    # stuffing IP that lands one correct credential out of many is
    # still suspicious).
    login_throttle_identifier_limit: int = Field(default=5)
    login_throttle_identifier_window_seconds: int = Field(default=900)
    login_throttle_ip_limit: int = Field(default=20)
    login_throttle_ip_window_seconds: int = Field(default=900)

    # Redis URL for the production throttle adapter. Empty on local —
    # the in-memory adapter is used instead (see container.py). When
    # APP_ENV=aws this is wired to an ElastiCache endpoint; a missing
    # value at AWS-time keeps the in-memory adapter, which fails open
    # so logins continue to function while operators wire it up.
    redis_url: str = Field(default="")

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
            object.__setattr__(
                self,
                "cors_allowed_origins",
                ["http://localhost:5173", "http://127.0.0.1:5173"],
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
