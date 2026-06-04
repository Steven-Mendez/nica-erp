"""Integration tests for the public invitations router.

Covers ``POST /v1/invitations/accept`` and
``GET /v1/invitations/{token}/preview`` — the two hash-fragment-safe
endpoints from ADR-0031. The router is mounted into a thin ``FastAPI``
instance with FastAPI ``dependency_overrides`` standing in for the use
case, repositories, token generator, and UoW so no Postgres is required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bootstrap.dependencies import get_request_uow
from contexts.identity.adapters.inbound.http.dependencies import get_current_user
from contexts.identity.application.ports.outbound import Identity
from contexts.tenants.adapters.inbound.http.dependencies import (
    get_accept_invitation,
    get_invitation_repository,
    get_invitation_token_generator,
    get_tenant_repository,
)
from contexts.tenants.adapters.inbound.http.errors import register_tenants_exception_handlers
from contexts.tenants.adapters.inbound.http.router import public_router
from contexts.tenants.application.use_cases import AcceptInvitation
from contexts.tenants.application.use_cases.accept_invitation import (
    AcceptInvitationCommand,
    AcceptInvitationResult,
)
from contexts.tenants.domain import (
    Invitation,
    InvitationIdentityMismatchError,
    Role,
)
from shared_kernel.adapters.context import CurrentUser

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")


class _FakeAcceptInvitation:
    """Stand-in for the AcceptInvitation use case."""

    def __init__(self) -> None:
        self.calls: list[AcceptInvitationCommand] = []
        self.result = AcceptInvitationResult(tenant_id=_TENANT_ID, role="accountant")

    async def execute(self, command: AcceptInvitationCommand) -> AcceptInvitationResult:
        self.calls.append(command)
        return self.result


class _FakeTokenGenerator:
    """Stand-in for the InvitationTokenGenerator port."""

    def __init__(self, *, raises_on_verify: bool = False) -> None:
        self.raises_on_verify = raises_on_verify

    def verify(self, *, token: str) -> None:
        if self.raises_on_verify:
            raise ValueError("bad token")

    def hash(self, *, token: str) -> str:
        return f"hash:{token}"

    def generate(self) -> tuple[str, str]:  # pragma: no cover — unused here
        raise NotImplementedError


class _FakeInvitationRepository:
    """Returns whatever invitation was preloaded for the requested hash."""

    def __init__(self, by_hash: dict[str, Invitation]) -> None:
        self.by_hash = by_hash

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        return self.by_hash.get(token_hash)


class _FakeTenantRepository:
    """Returns whatever tenant was preloaded for the requested id."""

    def __init__(self, by_id: dict[UUID, Any]) -> None:
        self.by_id = by_id

    async def get(self, tenant_id: UUID) -> Any:
        return self.by_id.get(tenant_id)


class _FakeUow:
    """Async-context-manager stub for the request UoW dependency."""

    def begin(self) -> _FakeUow:
        return self

    async def __aenter__(self) -> _FakeUow:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _make_invitation(
    *,
    email: str = "invitee@nica.test",
    status: str = "pending",
) -> Invitation:
    now = datetime.now(UTC)
    inv = Invitation.issue(
        tenant_id=_TENANT_ID,
        email=email,
        proposed_role=Role.ACCOUNTANT,
        token_hash="hash:tok",
        expires_at=now + timedelta(days=7),
        now=now,
    )
    inv.status = status  # type: ignore[assignment]
    return inv


def _build_app(
    *,
    accept_uc: AcceptInvitation | _FakeAcceptInvitation | None = None,
    token_gen: _FakeTokenGenerator | None = None,
    invitations: dict[str, Invitation] | None = None,
    tenants_by_id: dict[UUID, Any] | None = None,
    current_user_active_tenant: str | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(public_router)
    register_tenants_exception_handlers(app)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=_USER_ID,
        email="acceptor@nica.test",
        external_sub="cognito|sub",
        active_tenant=current_user_active_tenant,
    )
    app.dependency_overrides[get_request_uow] = lambda: _FakeUow()
    app.dependency_overrides[get_accept_invitation] = lambda: (
        accept_uc if accept_uc is not None else _FakeAcceptInvitation()
    )
    app.dependency_overrides[get_invitation_token_generator] = lambda: (
        token_gen if token_gen is not None else _FakeTokenGenerator()
    )
    app.dependency_overrides[get_invitation_repository] = lambda: _FakeInvitationRepository(
        invitations or {}
    )

    class _TenantStub:
        def __init__(self, name: str) -> None:
            self.name = name

    app.dependency_overrides[get_tenant_repository] = lambda: _FakeTenantRepository(
        tenants_by_id or {_TENANT_ID: _TenantStub("Empresa Demo")}
    )

    return app


@pytest.mark.integration
async def test_accept_endpoint_returns_tenant_and_role() -> None:
    accept = _FakeAcceptInvitation()
    app = _build_app(accept_uc=accept)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/invitations/accept", json={"token": "abc"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(_TENANT_ID)
    assert body["role"] == "accountant"
    assert len(accept.calls) == 1
    assert accept.calls[0].token == "abc"
    assert accept.calls[0].user_id == _USER_ID


@pytest.mark.integration
async def test_accept_endpoint_threads_caller_context_and_refresh_into_use_case() -> None:
    accept = _FakeAcceptInvitation()
    app = _build_app(accept_uc=accept, current_user_active_tenant="empresa-a-uuid")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # The refresh token now rides in the httpOnly cookie. The body
        # field stays accepted for one transition cycle (older SPA
        # builds) but the endpoint prefers the cookie when both exist.
        response = await client.post(
            "/v1/invitations/accept",
            json={"token": "abc"},
            cookies={"nica_erp_rt": "current-refresh"},
        )
    assert response.status_code == 200
    assert len(accept.calls) == 1
    cmd = accept.calls[0]
    assert cmd.token == "abc"
    assert cmd.user_id == _USER_ID
    assert cmd.user_email == "acceptor@nica.test"
    assert cmd.external_sub == "cognito|sub"
    # Critical: the prior_active_tenant value comes from the validated
    # CurrentUser context, not from any request body field.
    assert cmd.prior_active_tenant == "empresa-a-uuid"
    assert cmd.refresh_token == "current-refresh"


@pytest.mark.integration
async def test_accept_endpoint_serialises_rotated_tokens() -> None:
    accept = _FakeAcceptInvitation()
    accept.result = AcceptInvitationResult(
        tenant_id=_TENANT_ID,
        role="accountant",
        tokens=Identity(
            sub="11111111-1111-1111-1111-111111111111",
            email="acceptor@nica.test",
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
        ),
    )
    app = _build_app(accept_uc=accept)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/invitations/accept",
            json={"token": "abc"},
            cookies={"nica_erp_rt": "current-refresh"},
        )
    assert response.status_code == 200
    body = response.json()
    # JSON carries only access + id tokens; the rotated refresh token
    # is delivered via the `nica_erp_rt` Set-Cookie header (audit F-011).
    assert body["tokens"] == {
        "access_token": "new-access",
        "id_token": "new-id",
        "token_type": "Bearer",
    }
    set_cookie = response.headers.get("set-cookie", "")
    assert "nica_erp_rt=new-refresh" in set_cookie
    assert "HttpOnly" in set_cookie


@pytest.mark.integration
async def test_accept_endpoint_returns_null_tokens_when_use_case_omits_them() -> None:
    accept = _FakeAcceptInvitation()
    accept.result = AcceptInvitationResult(tenant_id=_TENANT_ID, role="accountant", tokens=None)
    app = _build_app(accept_uc=accept)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/invitations/accept", json={"token": "abc"})
    assert response.status_code == 200
    body = response.json()
    assert body["tokens"] is None


@pytest.mark.integration
async def test_accept_endpoint_returns_403_on_identity_mismatch() -> None:
    class _MismatchUC:
        async def execute(self, _command: AcceptInvitationCommand) -> AcceptInvitationResult:
            raise InvitationIdentityMismatchError()

    app = _build_app(accept_uc=_MismatchUC())  # type: ignore[arg-type]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/invitations/accept", json={"token": "abc"})
    assert response.status_code == 403, response.text
    body = response.json()
    assert body["code"] == "invitation.identity_mismatch"
    assert body["title"] == "Esta invitación no es para ti"
    # Detail SHALL NOT leak the JWT sub or any identifier.
    assert "detail" not in body or body["detail"] is None


@pytest.mark.integration
async def test_accept_endpoint_rejects_missing_token() -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/invitations/accept", json={})
    assert response.status_code == 422


@pytest.mark.integration
async def test_accept_endpoint_rejects_empty_token() -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/invitations/accept", json={"token": ""})
    assert response.status_code == 422


@pytest.mark.integration
async def test_accept_endpoint_rejects_extra_fields() -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/invitations/accept",
            json={"token": "abc", "unexpected": "x"},
        )
    assert response.status_code == 422


@pytest.mark.integration
async def test_preview_endpoint_returns_safe_metadata() -> None:
    invitation = _make_invitation(email="invitee@nica.test")
    app = _build_app(invitations={"hash:tok": invitation})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/invitations/tok/preview")
    assert response.status_code == 200, response.text
    body = response.json()
    # Audit F-026: preview SHALL omit the invitee email so anyone who
    # gets the link does not learn who was invited.
    assert body == {
        "organization_name": "Empresa Demo",
        "role": "accountant",
    }
    assert "email" not in body


@pytest.mark.integration
async def test_preview_endpoint_returns_404_when_token_invalid() -> None:
    app = _build_app(token_gen=_FakeTokenGenerator(raises_on_verify=True))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/invitations/bogus/preview")
    assert response.status_code == 404


@pytest.mark.integration
async def test_preview_endpoint_returns_404_when_invitation_missing() -> None:
    app = _build_app(invitations={})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/invitations/tok/preview")
    assert response.status_code == 404


@pytest.mark.integration
async def test_preview_endpoint_returns_404_when_invitation_not_pending() -> None:
    invitation = _make_invitation(status="cancelled")
    app = _build_app(invitations={"hash:tok": invitation})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/invitations/tok/preview")
    assert response.status_code == 404
