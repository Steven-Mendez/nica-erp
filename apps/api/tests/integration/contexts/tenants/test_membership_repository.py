"""Integration tests for :class:`MembershipRepositorySqlAlchemy`."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.tenants.adapters.outbound.persistence.sqlalchemy.membership_repository import (
    MembershipRepositorySqlAlchemy,
)
from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tenant_repository import (
    TenantRepositorySqlAlchemy,
)
from contexts.tenants.domain import (
    AuthorizationDgi,
    Membership,
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


async def _seed_user(session_factory: async_sessionmaker[AsyncSession], suffix: str = "") -> UUID:
    user_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            text("INSERT INTO users (id, external_sub, email) VALUES (:id, :sub, :email)"),
            {"id": user_id, "sub": str(user_id), "email": f"u{suffix}-{user_id}@test.dev"},
        )
        await session.commit()
    return user_id


async def _set_guc(uow: SqlAlchemyUnitOfWork, *, tenant_id: UUID, user_id: UUID) -> None:
    await uow.current_session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
    await uow.current_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )


@pytest.mark.integration
async def test_add_and_find_owner_roundtrip(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    user_id = await _seed_user(session_factory)

    now = datetime.now(UTC)
    owner = Membership.create_owner(user_id=user_id, tenant_id=tenant_id, now=now)

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_id)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        await repo.add(owner)

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_id)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.find(user_id=user_id, tenant_id=tenant_id)

    assert loaded is not None
    assert loaded.role is Role.OWNER
    assert loaded.status == "active"


@pytest.mark.integration
async def test_tenant_members_self_policy_lets_user_see_own_row_without_tenant_guc(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The ``tenant_members_self`` policy's first USING branch."""

    tenant_id = await _seed_tenant(isolated_uow)
    user_id = await _seed_user(session_factory)

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_id)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        await repo.add(
            Membership.create_owner(user_id=user_id, tenant_id=tenant_id, now=datetime.now(UTC))
        )

    # ``app.tenant_id`` is the zero-uuid sentinel but the policy still
    # lets the user read their own row via the user_id branch.
    async with isolated_uow.begin():
        await isolated_uow.current_session.execute(
            text("SELECT set_config('app.tenant_id', '00000000-0000-0000-0000-000000000000', true)")
        )
        await isolated_uow.current_session.execute(
            text("SELECT set_config('app.current_user_id', :u, true)"),
            {"u": str(user_id)},
        )
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        rows = await repo.list_active_for_user(user_id)

    assert len(rows) == 1
    assert rows[0].tenant_id == tenant_id


@pytest.mark.integration
async def test_update_persists_role_change(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    user_id = await _seed_user(session_factory)

    now = datetime.now(UTC)
    member = Membership.join(user_id=user_id, tenant_id=tenant_id, role=Role.VIEWER, now=now)

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_id)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        await repo.add(member)

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_id)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.find(user_id=user_id, tenant_id=tenant_id)
        assert loaded is not None
        loaded.change_role(new_role=Role.ADMIN)
        await repo.update(loaded)

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_id)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        reloaded = await repo.find(user_id=user_id, tenant_id=tenant_id)
    assert reloaded is not None
    assert reloaded.role is Role.ADMIN
