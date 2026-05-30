"""Integration tests for :class:`InvitationRepositorySqlAlchemy`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from contexts.tenants.adapters.outbound.persistence.sqlalchemy.invitation_repository import (
    InvitationRepositorySqlAlchemy,
)
from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tenant_repository import (
    TenantRepositorySqlAlchemy,
)
from contexts.tenants.domain import (
    AuthorizationDgi,
    Invitation,
    Municipality,
    Regime,
    Role,
    Ruc,
    Tenant,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


async def _seed_tenant(uow: SqlAlchemyUnitOfWork) -> UUID:
    tenant = Tenant.register(
        name="Empresa Z",
        ruc=Ruc.parse("0010101800010X"),
        regime=Regime("general"),
        municipality=Municipality("Managua"),
        authorization_dgi=AuthorizationDgi(
            number="A",
            valid_from=datetime.now(UTC).date(),
            valid_to=datetime.now(UTC).date(),
        ),
        fiscal_address="addr",
        is_withholder=False,
        now=datetime.now(UTC),
        id_=uuid4(),
    )
    async with uow.begin():
        await TenantRepositorySqlAlchemy(uow).add(tenant)
    return tenant.id


async def _set_tenant_guc(uow: SqlAlchemyUnitOfWork, tenant_id: UUID) -> None:
    await uow.current_session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )


@pytest.mark.integration
async def test_add_and_get_by_token_hash(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    now = datetime.now(UTC)
    invitation = Invitation.issue(
        tenant_id=tenant_id,
        email="invitee@test.dev",
        proposed_role=Role.ACCOUNTANT,
        token_hash="hash-1",
        expires_at=now + timedelta(days=7),
        now=now,
    )

    async with isolated_uow.begin():
        await _set_tenant_guc(isolated_uow, tenant_id)
        repo = InvitationRepositorySqlAlchemy(isolated_uow)
        await repo.add(invitation)

    async with isolated_uow.begin():
        await _set_tenant_guc(isolated_uow, tenant_id)
        repo = InvitationRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.get_by_token_hash("hash-1")

    assert loaded is not None
    assert loaded.email == "invitee@test.dev"
    assert loaded.proposed_role is Role.ACCOUNTANT


@pytest.mark.integration
async def test_list_by_tenant_returns_only_matching_rows(
    isolated_uow: SqlAlchemyUnitOfWork,
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    now = datetime.now(UTC)
    async with isolated_uow.begin():
        await _set_tenant_guc(isolated_uow, tenant_id)
        repo = InvitationRepositorySqlAlchemy(isolated_uow)
        for i, email in enumerate(["x@test.dev", "y@test.dev"]):
            await repo.add(
                Invitation.issue(
                    tenant_id=tenant_id,
                    email=email,
                    proposed_role=Role.VIEWER,
                    token_hash=f"hash-{i}",
                    expires_at=now + timedelta(days=1),
                    now=now,
                )
            )

    async with isolated_uow.begin():
        await _set_tenant_guc(isolated_uow, tenant_id)
        repo = InvitationRepositorySqlAlchemy(isolated_uow)
        rows = await repo.list_by_tenant(tenant_id)

    assert len(rows) == 2
    assert {r.email for r in rows} == {"x@test.dev", "y@test.dev"}
