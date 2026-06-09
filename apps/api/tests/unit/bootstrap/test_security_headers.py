"""Unit tests for :class:`SecurityHeadersMiddleware`."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from bootstrap.api import create_app
from bootstrap.container import build_identity_provider_for_middleware
from bootstrap.security_headers import SecurityHeadersMiddleware
from bootstrap.settings import get_settings


def _mini_app() -> Starlette:
    async def plain(request):  # type: ignore[no-untyped-def]
        return PlainTextResponse("ok")

    async def cached(request):  # type: ignore[no-untyped-def]
        return PlainTextResponse("ok", headers={"x-frame-options": "SAMEORIGIN"})

    app = Starlette(
        routes=[
            Route("/v1/auth/login", plain, methods=["GET"]),
            Route("/v1/things", plain, methods=["GET"]),
            Route("/v1/custom", cached, methods=["GET"]),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware, auth_path_prefix="/v1/auth")
    return app


class TestMiddlewareIsolated:
    def test_baseline_headers_on_every_response(self) -> None:
        client = TestClient(_mini_app())
        response = client.get("/v1/things")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"

    def test_no_store_only_under_auth_prefix(self) -> None:
        client = TestClient(_mini_app())
        assert client.get("/v1/auth/login").headers["cache-control"] == "no-store"
        assert "cache-control" not in client.get("/v1/things").headers

    def test_setdefault_does_not_override_handler_header(self) -> None:
        client = TestClient(_mini_app())
        assert client.get("/v1/custom").headers["x-frame-options"] == "SAMEORIGIN"


class TestCreateApp:
    def test_headers_present_on_auth_middleware_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The middleware is outermost: even short-circuited 401s carry it."""

        monkeypatch.setenv("APP_ENV", "local")
        get_settings.cache_clear()
        build_identity_provider_for_middleware.cache_clear()

        app = create_app()
        client = TestClient(app)
        response = client.get("/v1/me")

        assert response.status_code == 401
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"

    def test_auth_prefix_no_store_via_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "local")
        get_settings.cache_clear()
        build_identity_provider_for_middleware.cache_clear()

        app = create_app()
        client = TestClient(app)
        # 422 (missing body) is fine — only the headers matter here.
        response = client.post("/v1/auth/login")

        assert response.headers["cache-control"] == "no-store"
