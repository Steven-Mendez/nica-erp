"""Integration tests for :class:`TenantMiddleware`.

Mounts the middleware against a thin ``FastAPI`` app with a stub
``uow_factory`` so no Postgres is required. The middleware delegates
membership lookup to a SQL query — the stub answers either ``1`` (hit)
or ``None`` (miss) depending on the scenario.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from contexts.tenants.adapters.inbound.http.middleware import TenantMiddleware
from shared_kernel.adapters.context import CurrentUser, CurrentUserContext, TenantContext

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")


class _StubResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _StubSession:
    def __init__(self, hit: Any) -> None:
        self._hit = hit
        self.executed: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, stmt: Any, params: dict[str, Any]) -> _StubResult:
        # `stmt` is a sqlalchemy `text(...)`; stringify for assertion convenience.
        self.executed.append((str(stmt), params))
        return _StubResult(self._hit)


class _StubUow:
    def __init__(self, hit: Any) -> None:
        self._session = _StubSession(hit)
        self.begin_called = 0

    def begin(self) -> _StubUow:
        self.begin_called += 1
        return self

    async def __aenter__(self) -> _StubSession:
        return self._session

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _build_app(
    *,
    current_user: CurrentUser | None,
    membership_hit: Any = 1,
) -> tuple[FastAPI, _StubUow]:
    uow = _StubUow(hit=membership_hit)
    app = FastAPI()
    app.add_middleware(TenantMiddleware, uow_factory=lambda: uow)  # type: ignore[arg-type]

    @app.middleware("http")
    async def _seed_current_user(request: Any, call_next: Any) -> Any:
        # Starlette runs `add_middleware` in reverse order; this
        # outer-most middleware sets the ContextVar before the
        # TenantMiddleware reads it (matching how AuthMiddleware
        # behaves in production).
        if current_user is not None:
            CurrentUserContext.set(current_user)  # type: ignore[func-returns-value]
        try:
            return await call_next(request)
        finally:
            if current_user is not None:
                CurrentUserContext.clear()

    @app.get("/healthz")
    async def _healthz() -> JSONResponse:
        # Reached unauthenticated; middleware should bypass.
        return JSONResponse({"ok": True})

    @app.get("/v1/me")
    async def _me() -> JSONResponse:
        # No-tenant-required allowlist; bypass to handler with no tenant set.
        return JSONResponse({"tenant": str(TenantContext.get() or "")})

    @app.get("/v1/widgets")
    async def _widgets() -> JSONResponse:
        # Tenant-required route; handler echoes what was pinned.
        return JSONResponse({"tenant": str(TenantContext.get() or "")})

    return app, uow


def _ctx_user(active_tenant: str | None) -> CurrentUser:
    return CurrentUser(
        user_id=_USER_ID,
        email="ada@nica.test",
        external_sub="cognito|sub",
        active_tenant=active_tenant,
    )


@pytest.mark.integration
async def test_unauthenticated_allowlist_bypasses_middleware() -> None:
    app, uow = _build_app(current_user=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert uow.begin_called == 0


@pytest.mark.integration
async def test_no_tenant_required_allowlist_passes_through_without_pinning() -> None:
    user = _ctx_user(active_tenant=None)
    app, uow = _build_app(current_user=user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me")
    assert response.status_code == 200
    assert response.json() == {"tenant": ""}
    # /v1/me is on the no-tenant-required allowlist, so the middleware
    # short-circuits before opening the UoW.
    assert uow.begin_called == 0


@pytest.mark.integration
async def test_missing_current_user_returns_defensive_401() -> None:
    app, _ = _build_app(current_user=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/widgets")
    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_credentials"


@pytest.mark.integration
async def test_invalid_uuid_active_tenant_returns_403_not_member() -> None:
    user = _ctx_user(active_tenant="not-a-uuid")
    app, _ = _build_app(current_user=user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/widgets")
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "tenant.not_member"


@pytest.mark.integration
async def test_no_membership_row_returns_403_not_member() -> None:
    user = _ctx_user(active_tenant=str(_TENANT_ID))
    app, uow = _build_app(current_user=user, membership_hit=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/widgets")
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "tenant.not_member"
    assert uow.begin_called == 1
    # The middleware should have queried `tenant_members` with the
    # user + tenant pulled from the JWT claim.
    stmt, params = uow._session.executed[-1]
    assert "tenant_members" in stmt
    assert params == {"user_id": _USER_ID, "tenant_id": _TENANT_ID}


@pytest.mark.integration
async def test_valid_membership_pins_tenant_context_and_reaches_handler() -> None:
    user = _ctx_user(active_tenant=str(_TENANT_ID))
    app, uow = _build_app(current_user=user, membership_hit=1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/widgets")
    assert response.status_code == 200
    # The handler observed the pinned TenantContext.
    assert response.json() == {"tenant": str(_TENANT_ID)}
    assert uow.begin_called == 1


@pytest.mark.integration
async def test_tenant_context_is_cleared_after_request() -> None:
    user = _ctx_user(active_tenant=str(_TENANT_ID))
    app, _ = _build_app(current_user=user, membership_hit=1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/widgets")
    assert response.status_code == 200
    # After the request returns the ContextVar should be cleared so the
    # next request starts from a clean slate.
    assert TenantContext.get() is None
