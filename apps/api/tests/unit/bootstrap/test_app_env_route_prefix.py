"""Unit tests for the AWS-vs-local route prefix.

CloudFront's `/api/*` behavior forwards the full path to the ALB without
stripping the prefix, so when `APP_ENV=aws` the FastAPI app mounts every
router under `/api`. Locally the routes mount at root so sprint 00's
`/healthz` contract still holds.
"""

from __future__ import annotations

import pytest

from bootstrap.api import create_app
from bootstrap.container import build_identity_provider_for_middleware
from bootstrap.settings import get_settings


def _route_paths(app) -> set[str]:  # type: ignore[no-untyped-def]
    return {getattr(r, "path", "") for r in app.routes}


class TestLocalPrefix:
    def test_healthz_mounted_at_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "local")
        get_settings.cache_clear()
        build_identity_provider_for_middleware.cache_clear()

        app = create_app()
        paths = _route_paths(app)
        assert "/healthz" in paths
        assert "/api/healthz" not in paths


class TestAwsPrefix:
    def test_healthz_mounted_under_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "aws")
        get_settings.cache_clear()
        build_identity_provider_for_middleware.cache_clear()

        app = create_app()
        paths = _route_paths(app)
        assert "/api/healthz" in paths
        assert "/healthz" not in paths
