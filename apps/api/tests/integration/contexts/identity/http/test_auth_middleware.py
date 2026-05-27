"""Integration tests for :class:`AuthMiddleware` and the allowlist.

These exercise the middleware against a thin ``FastAPI`` instance — no
testcontainer Postgres required. We swap in a fake
:class:`IdentityProvider` whose ``verify_token`` echoes the supplied
claims so the suite can assert middleware behaviour without minting real
JWTs.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from contexts.identity.adapters.inbound.http.errors import register_exception_handlers
from contexts.identity.adapters.inbound.http.middleware import AuthMiddleware
from contexts.identity.application.errors import (
    InvalidCredentialsError,
    TokenExpiredError,
)
from contexts.identity.application.ports.outbound import Identity

_VALID_SUB = "11111111-1111-1111-1111-111111111111"


class _FakeIdentityProvider:
    """Echo verify_token; raise on anything else."""

    def __init__(self, claims: dict[str, Any] | None = None) -> None:
        self._claims = claims or {
            "sub": _VALID_SUB,
            "email": "a@b.io",
            "custom:active_tenant": "tenant-1",
        }
        self.invalid = False

    async def verify_token(self, *, token: str) -> dict[str, Any]:
        if self.invalid:
            raise InvalidCredentialsError("bad token")
        if token == "expired":
            raise TokenExpiredError("expired")
        if token == "bad":
            raise InvalidCredentialsError("bad token")
        return self._claims

    # The other methods are unused for middleware tests, but the Protocol
    # is runtime_checkable so we keep them present as stubs.
    async def register(self, *, email: str, password: str) -> str:  # pragma: no cover
        raise NotImplementedError

    async def authenticate(self, *, email: str, password: str) -> Identity:  # pragma: no cover
        raise NotImplementedError

    async def refresh(self, *, refresh_token: str) -> Identity:  # pragma: no cover
        raise NotImplementedError

    async def confirm_signup(self, *, email: str, code: str) -> str:  # pragma: no cover
        raise NotImplementedError

    async def resend_confirmation(self, *, email: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def forgot_password(self, *, email: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def confirm_forgot_password(
        self, *, email: str, code: str, new_password: str
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def change_password(
        self, *, access_token: str, old_password: str, new_password: str
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def global_signout(self, *, external_sub: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def update_active_tenant(
        self, *, external_sub: str, tenant_id: str
    ) -> None:  # pragma: no cover
        raise NotImplementedError


def _build_app(idp: _FakeIdentityProvider) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, identity_provider=idp)  # type: ignore[arg-type]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    @app.get("/healthz")
    async def _healthz() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/v1/me")
    async def _me() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.post("/v1/auth/login")
    async def _login() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.post("/v1/auth/logout")
    async def _logout() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/v1/widgets")
    async def _widgets() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.post("/v1/invitations/{token}/accept")
    async def _accept(token: str) -> JSONResponse:
        return JSONResponse({"ok": True, "token": token})

    return app


@pytest.mark.integration
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/healthz"),
        ("POST", "/v1/auth/login"),
        ("POST", "/v1/invitations/abc-123/accept"),
    ],
)
async def test_unauthenticated_allowlist_skips_middleware(method: str, path: str) -> None:
    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == 200, response.text


@pytest.mark.integration
async def test_missing_authorization_returns_401_problem_detail() -> None:
    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "auth.invalid_credentials"


@pytest.mark.integration
async def test_expired_token_maps_to_token_expired_code() -> None:
    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me", headers={"Authorization": "Bearer expired"})
    assert response.status_code == 401
    assert response.json()["code"] == "auth.token_expired"


@pytest.mark.integration
async def test_invalid_token_maps_to_invalid_credentials_code() -> None:
    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_credentials"


@pytest.mark.integration
async def test_valid_token_reaches_handler() -> None:
    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me", headers={"Authorization": "Bearer good"})
    assert response.status_code == 200


@pytest.mark.integration
async def test_tenantless_jwt_can_reach_me() -> None:
    idp = _FakeIdentityProvider(
        claims={
            "sub": _VALID_SUB,
            "email": "a@b.io",
            "custom:active_tenant": "",
        }
    )
    app = _build_app(idp)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me", headers={"Authorization": "Bearer good"})
    assert response.status_code == 200


@pytest.mark.integration
async def test_tenantless_jwt_blocked_on_arbitrary_route() -> None:
    idp = _FakeIdentityProvider(
        claims={
            "sub": _VALID_SUB,
            "email": "a@b.io",
            "custom:active_tenant": "",
        }
    )
    app = _build_app(idp)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/widgets", headers={"Authorization": "Bearer good"})
    assert response.status_code == 403
    assert response.json()["code"] == "tenant.required"


@pytest.mark.integration
async def test_tenantless_jwt_can_reach_logout() -> None:
    idp = _FakeIdentityProvider(
        claims={
            "sub": _VALID_SUB,
            "email": "a@b.io",
            "custom:active_tenant": "",
        }
    )
    app = _build_app(idp)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/auth/logout", headers={"Authorization": "Bearer good"})
    assert response.status_code == 200


@pytest.mark.integration
async def test_401_response_carries_cors_headers() -> None:
    """CORS must be OUTERMOST so the 401 from auth still carries
    ``access-control-allow-origin``.
    """

    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.integration
async def test_api_prefix_is_stripped_for_allowlist() -> None:
    """In AWS, paths are mounted under ``/api``; the middleware MUST normalise."""

    app = _build_app(_FakeIdentityProvider())
    transport = ASGITransport(app=app)
    # Register a duplicate route under /api/healthz to simulate AWS mount.
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # The /api-prefixed route doesn't exist on this test app, but the
        # middleware would have allowed it through to the route layer
        # (returning 404). We assert no 401 sneaks in.
        response = await client.get("/api/healthz")
    # Not 401: the middleware let the request reach FastAPI's router (which
    # then 404s because the route isn't registered).
    assert response.status_code != 401
