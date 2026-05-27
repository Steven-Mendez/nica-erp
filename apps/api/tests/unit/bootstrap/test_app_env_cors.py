"""Unit tests for the AWS-vs-local CORS toggle.

Behind CloudFront the SPA and API share one origin, so CORS is a no-op and
the allow-list is empty. Locally the Vite dev server (:5173) calls uvicorn
(:8000) cross-origin and the middleware mounts with the explicit allow-list.
"""

from __future__ import annotations

import pytest
from starlette.middleware.cors import CORSMiddleware

from bootstrap.api import create_app
from bootstrap.container import build_identity_provider_for_middleware
from bootstrap.settings import Settings, get_settings


def _has_cors_middleware(app) -> bool:  # type: ignore[no-untyped-def]
    return any(m.cls is CORSMiddleware for m in app.user_middleware)


class TestLocalDefaults:
    def test_settings_default_to_localhost_allow_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.app_env == "local"
        assert settings.cors_allowed_origins == ["http://localhost:5173"]

    def test_local_app_mounts_cors_middleware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "local")
        get_settings.cache_clear()
        build_identity_provider_for_middleware.cache_clear()

        app = create_app()
        assert _has_cors_middleware(app)


class TestAwsDefaults:
    def test_app_env_aws_empties_cors_allow_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "aws")
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        get_settings.cache_clear()

        # Bypass the repo-root `.env.local` (which always supplies
        # CORS_ALLOWED_ORIGINS for dev) so the AWS-default assertion holds.
        settings = Settings(_env_file=None)
        assert settings.app_env == "aws"
        assert settings.cors_allowed_origins == []

    def test_aws_app_does_not_mount_cors_middleware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "aws")
        get_settings.cache_clear()
        build_identity_provider_for_middleware.cache_clear()

        app = create_app()
        assert not _has_cors_middleware(app)


class TestExplicitOverrides:
    def test_local_override_via_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://app.example.com"]')
        get_settings.cache_clear()

        settings = Settings()
        assert settings.cors_allowed_origins == ["https://app.example.com"]

    def test_aws_override_via_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If an operator deliberately sets CORS in AWS, respect it."""
        monkeypatch.setenv("APP_ENV", "aws")
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://override.example.com"]')
        get_settings.cache_clear()

        settings = Settings()
        assert settings.cors_allowed_origins == ["https://override.example.com"]
