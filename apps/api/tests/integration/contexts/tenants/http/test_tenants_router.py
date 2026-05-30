"""Integration tests for the authenticated tenants router.

Covers each of the eleven routes mounted by ``router`` with at least
the happy path (200 / 201 / 204). For the eight routes that depend on
``require(<permission>)`` we also assert that an actor lacking the
permission is rejected with a 403 ``missing-permission`` problem
detail.

The 401 leg is covered by the dedicated middleware test
(``test_auth_middleware.py``) and the 404 cross-tenant leg by the
RLS e2e test, so this suite focuses on what the router itself owns:
parameter binding, permission gating, and response shaping.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bootstrap.db import get_uow as get_request_uow_db
from bootstrap.dependencies import current_actor
from bootstrap.dependencies import get_request_uow as get_shared_request_uow
from contexts.identity.adapters.inbound.http.dependencies import get_current_user
from contexts.identity.application.ports.outbound.identity_provider import Identity
from contexts.tenants.adapters.inbound.http.dependencies import (
    get_accept_invitation,
    get_cancel_invitation,
    get_create_tenant,
    get_get_my_tenants,
    get_get_tenant,
    get_invite_member,
    get_list_invitations,
    get_list_members,
    get_remove_member,
    get_switch_active_tenant,
    get_update_member_role,
    get_update_tenant,
)
from contexts.tenants.adapters.inbound.http.errors import register_tenants_exception_handlers
from contexts.tenants.adapters.inbound.http.router import router
from contexts.tenants.application.use_cases.create_tenant import CreateTenantResult
from contexts.tenants.application.use_cases.get_my_tenants import MyTenantView
from contexts.tenants.application.use_cases.invite_member import InviteMemberResult
from contexts.tenants.domain import Membership, Role, Tenant
from shared_kernel.adapters.context import CurrentUser
from shared_kernel.permissions import Actor

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
_OTHER_USER_ID = UUID("33333333-3333-3333-3333-333333333333")
_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
_INVITATION_ID = UUID("44444444-4444-4444-4444-444444444444")


def _make_tenant() -> Tenant:
    now = datetime.now(UTC)
    return Tenant.register(name="Empresa Demo", is_withholder=False, now=now, id_=_TENANT_ID)


# --- stubs ----------------------------------------------------------------


class _StubCreateTenant:
    async def execute(self, command: Any) -> CreateTenantResult:
        now = datetime.now(UTC)
        return CreateTenantResult(
            tenant_id=_TENANT_ID,
            name="Empresa Demo",
            status="active",
            created_at=now,
            updated_at=now,
        )


class _StubGetTenant:
    async def execute(self, tenant_id: UUID) -> Tenant:
        return _make_tenant()


class _StubUpdateTenant:
    async def execute(self, command: Any) -> Tenant:
        return _make_tenant()


class _StubGetMyTenants:
    async def execute(self, user_id: UUID) -> list[MyTenantView]:
        return [
            MyTenantView(
                tenant_id=_TENANT_ID,
                name="Empresa Demo",
                role=Role.OWNER,
                status="active",
                joined_at=datetime.now(UTC),
            )
        ]


class _StubSwitchActiveTenant:
    async def execute(self, command: Any) -> Identity:
        return Identity(
            sub="sub-1",
            email="ada@nica.test",
            access_token="acc",
            refresh_token="ref",
            id_token="idt",
            claims={},
        )


class _StubListMembers:
    async def execute(self, tenant_id: UUID) -> list[Membership]:
        now = datetime.now(UTC)
        return [
            Membership.create_owner(
                user_id=_USER_ID,
                tenant_id=tenant_id,
                now=now,
            )
        ]


class _StubUpdateMemberRole:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def execute(self, command: Any) -> None:
        self.calls.append(command)


class _StubRemoveMember:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def execute(self, command: Any) -> None:
        self.calls.append(command)


class _StubListInvitations:
    async def execute(self, tenant_id: UUID) -> list[Any]:
        return []


class _StubInviteMember:
    async def execute(self, command: Any) -> InviteMemberResult:
        return InviteMemberResult(
            invitation_id=_INVITATION_ID,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )


class _StubCancelInvitation:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def execute(self, command: Any) -> None:
        self.calls.append(command)


class _StubAcceptInvitation:  # unused here — public router has its own test
    async def execute(self, command: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class _StubUow:
    """`async with uow.begin()` no-op so list_members can run."""

    def begin(self) -> _StubUow:
        return self

    async def __aenter__(self) -> _StubUow:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


# --- app factory ----------------------------------------------------------


def _build_app(*, permissions: frozenset[str] = frozenset()) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    register_tenants_exception_handlers(app)

    actor = Actor(user_id=_USER_ID, tenant_id=_TENANT_ID, role="owner", permissions=permissions)
    app.dependency_overrides[current_actor] = lambda: actor
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=_USER_ID,
        email="ada@nica.test",
        external_sub="cognito|sub",
        active_tenant=str(_TENANT_ID),
    )
    app.dependency_overrides[get_request_uow_db] = lambda: _StubUow()
    app.dependency_overrides[get_shared_request_uow] = lambda: _StubUow()

    # Use cases.
    app.dependency_overrides[get_create_tenant] = lambda: _StubCreateTenant()
    app.dependency_overrides[get_get_tenant] = lambda: _StubGetTenant()
    app.dependency_overrides[get_update_tenant] = lambda: _StubUpdateTenant()
    app.dependency_overrides[get_get_my_tenants] = lambda: _StubGetMyTenants()
    app.dependency_overrides[get_switch_active_tenant] = lambda: _StubSwitchActiveTenant()
    app.dependency_overrides[get_list_members] = lambda: _StubListMembers()
    app.dependency_overrides[get_update_member_role] = lambda: _StubUpdateMemberRole()
    app.dependency_overrides[get_remove_member] = lambda: _StubRemoveMember()
    app.dependency_overrides[get_list_invitations] = lambda: _StubListInvitations()
    app.dependency_overrides[get_invite_member] = lambda: _StubInviteMember()
    app.dependency_overrides[get_cancel_invitation] = lambda: _StubCancelInvitation()
    app.dependency_overrides[get_accept_invitation] = lambda: _StubAcceptInvitation()

    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- happy-path coverage --------------------------------------------------


@pytest.mark.integration
async def test_post_create_tenant_returns_201() -> None:
    app = _build_app()
    async with _client(app) as c:
        r = await c.post("/v1/tenants", json={"name": "Empresa Demo"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == str(_TENANT_ID)
    assert body["name"] == "Empresa Demo"


@pytest.mark.integration
async def test_get_my_tenants_returns_membership_list() -> None:
    app = _build_app()
    async with _client(app) as c:
        r = await c.get("/v1/tenants/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"][0]["tenant_id"] == str(_TENANT_ID)
    assert body["items"][0]["role"] == "owner"


@pytest.mark.integration
async def test_get_tenant_returns_200_with_permission() -> None:
    app = _build_app(permissions=frozenset({"tenant:read"}))
    async with _client(app) as c:
        r = await c.get(f"/v1/tenants/{_TENANT_ID}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(_TENANT_ID)


@pytest.mark.integration
async def test_patch_tenant_returns_200_with_permission() -> None:
    app = _build_app(permissions=frozenset({"tenant:write"}))
    async with _client(app) as c:
        r = await c.patch(
            f"/v1/tenants/{_TENANT_ID}",
            json={"name": "Empresa Demo"},
        )
    assert r.status_code == 200, r.text


@pytest.mark.integration
async def test_post_switch_tenant_returns_token_bundle() -> None:
    app = _build_app()
    async with _client(app) as c:
        r = await c.post(
            f"/v1/tenants/{_TENANT_ID}/switch",
            json={"refresh_token": "ref"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] == "acc"
    assert body["token_type"] == "Bearer"


@pytest.mark.integration
async def test_get_members_returns_list_with_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    # The list_members route instantiates UserRepositorySqlAlchemy directly
    # for cross-context user enrichment (display_name + email). Stub its
    # `get_by_id` so we don't need a real session.
    async def _fake_get_by_id(self: Any, user_id: UUID) -> None:
        return None

    monkeypatch.setattr(
        "contexts.identity.adapters.outbound.persistence.sqlalchemy.user_repository."
        "UserRepositorySqlAlchemy.get_by_id",
        _fake_get_by_id,
    )

    app = _build_app(permissions=frozenset({"members:read"}))
    async with _client(app) as c:
        r = await c.get(f"/v1/tenants/{_TENANT_ID}/members")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert body[0]["user_id"] == str(_USER_ID)
    assert body[0]["role"] == "owner"


@pytest.mark.integration
async def test_patch_member_role_returns_204_with_permission() -> None:
    app = _build_app(permissions=frozenset({"members:update-role"}))
    async with _client(app) as c:
        r = await c.patch(
            f"/v1/tenants/{_TENANT_ID}/members/{_OTHER_USER_ID}",
            json={"role": "viewer"},
        )
    assert r.status_code == 204, r.text


@pytest.mark.integration
async def test_delete_member_returns_204_with_permission() -> None:
    app = _build_app(permissions=frozenset({"members:remove"}))
    async with _client(app) as c:
        r = await c.delete(f"/v1/tenants/{_TENANT_ID}/members/{_OTHER_USER_ID}")
    assert r.status_code == 204, r.text


@pytest.mark.integration
async def test_get_invitations_returns_list_with_permission() -> None:
    app = _build_app(permissions=frozenset({"members:read"}))
    async with _client(app) as c:
        r = await c.get(f"/v1/tenants/{_TENANT_ID}/invitations")
    assert r.status_code == 200, r.text
    assert r.json() == []


@pytest.mark.integration
async def test_post_invitation_returns_201_with_permission() -> None:
    app = _build_app(permissions=frozenset({"members:invite"}))
    async with _client(app) as c:
        r = await c.post(
            f"/v1/tenants/{_TENANT_ID}/invitations",
            json={"email": "invitee@nica.test", "proposed_role": "accountant"},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == str(_INVITATION_ID)
    assert body["email"] == "invitee@nica.test"
    assert body["proposed_role"] == "accountant"
    assert body["status"] == "pending"


@pytest.mark.integration
async def test_delete_invitation_returns_204_with_permission() -> None:
    app = _build_app(permissions=frozenset({"members:invite"}))
    async with _client(app) as c:
        r = await c.delete(
            f"/v1/tenants/{_TENANT_ID}/invitations/{_INVITATION_ID}",
        )
    assert r.status_code == 204, r.text


# --- 403 coverage for routes guarded by require(<perm>) -------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "method,path,body,permission",
    [
        ("GET", f"/v1/tenants/{_TENANT_ID}", None, "tenant:read"),
        ("PATCH", f"/v1/tenants/{_TENANT_ID}", {"name": "x"}, "tenant:write"),
        ("GET", f"/v1/tenants/{_TENANT_ID}/members", None, "members:read"),
        (
            "PATCH",
            f"/v1/tenants/{_TENANT_ID}/members/{_OTHER_USER_ID}",
            {"role": "viewer"},
            "members:update-role",
        ),
        (
            "DELETE",
            f"/v1/tenants/{_TENANT_ID}/members/{_OTHER_USER_ID}",
            None,
            "members:remove",
        ),
        ("GET", f"/v1/tenants/{_TENANT_ID}/invitations", None, "members:read"),
        (
            "POST",
            f"/v1/tenants/{_TENANT_ID}/invitations",
            {"email": "x@y.com", "proposed_role": "viewer"},
            "members:invite",
        ),
        (
            "DELETE",
            f"/v1/tenants/{_TENANT_ID}/invitations/{_INVITATION_ID}",
            None,
            "members:invite",
        ),
    ],
)
async def test_route_returns_403_when_actor_lacks_permission(
    method: str, path: str, body: dict[str, Any] | None, permission: str
) -> None:
    # Actor with NO permissions — every guarded route must respond 403.
    app = _build_app(permissions=frozenset())
    async with _client(app) as c:
        r = await c.request(method, path, json=body)
    assert r.status_code == 403, r.text
    payload = r.json()
    assert payload["code"] == "missing-permission"
    assert permission in payload["missing"]
