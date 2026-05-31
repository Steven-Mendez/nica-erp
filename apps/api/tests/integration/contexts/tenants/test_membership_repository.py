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
from contexts.tenants.application.use_cases.list_members import ListMembersQuery
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


async def _seed_user_full(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    display_name: str,
    email: str,
) -> UUID:
    user_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, external_sub, email, display_name) "
                "VALUES (:id, :sub, :email, :display_name)"
            ),
            {
                "id": user_id,
                "sub": str(user_id),
                "email": email,
                "display_name": display_name,
            },
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


@pytest.mark.integration
async def test_list_page_joins_user_profile_and_paginates(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    # Seed 5 distinct members with controlled display_name + email.
    user_ids = []
    for i in range(5):
        uid = await _seed_user_full(
            session_factory,
            display_name=f"User {i:02d}",
            email=f"user{i:02d}@nica.test",
        )
        user_ids.append(uid)
    now = datetime.now(UTC)
    async with isolated_uow.begin():
        # No GUC set — `tenant_members_self` policy still allows
        # writes scoped by user_id branch when reading, but writes
        # need the tenant GUC to satisfy WITH CHECK.
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_ids[0])
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        for i, uid in enumerate(user_ids):
            m = (
                Membership.create_owner(user_id=uid, tenant_id=tenant_id, now=now)
                if i == 0
                else Membership.join(user_id=uid, tenant_id=tenant_id, role=Role.VIEWER, now=now)
            )
            await repo.add(m)

    # First page of 2 — default sort joined_at ASC.
    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=user_ids[0])
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        items, total = await repo.list_page(
            ListMembersQuery(tenant_id=tenant_id, limit=2, offset=0)
        )
    assert total == 5
    assert len(items) == 2
    # JOIN populates display_name + email.
    assert items[0].display_name is not None
    assert items[0].email is not None


@pytest.mark.integration
async def test_list_page_q_matches_across_display_name_and_email(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    ada = await _seed_user_full(session_factory, display_name="Ada Lovelace", email="ada@nica.test")
    bob = await _seed_user_full(session_factory, display_name="Bob Builder", email="bob@nica.test")
    carla = await _seed_user_full(
        session_factory, display_name="Carla", email="carla-ada@nica.test"
    )
    now = datetime.now(UTC)
    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=ada)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        await repo.add(Membership.create_owner(user_id=ada, tenant_id=tenant_id, now=now))
        await repo.add(Membership.join(user_id=bob, tenant_id=tenant_id, role=Role.VIEWER, now=now))
        await repo.add(
            Membership.join(user_id=carla, tenant_id=tenant_id, role=Role.VIEWER, now=now)
        )

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=ada)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        items, total = await repo.list_page(ListMembersQuery(tenant_id=tenant_id, q="ada"))

    # Matches Ada (display_name) and Carla (email).
    matched_ids = {it.user_id for it in items}
    assert matched_ids == {ada, carla}
    assert total == 2


@pytest.mark.integration
async def test_list_page_filters_by_role_and_status(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    owner = await _seed_user_full(session_factory, display_name="O", email="o@x")
    admin = await _seed_user_full(session_factory, display_name="A", email="a@x")
    viewer = await _seed_user_full(session_factory, display_name="V", email="v@x")
    now = datetime.now(UTC)
    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=owner)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        await repo.add(Membership.create_owner(user_id=owner, tenant_id=tenant_id, now=now))
        await repo.add(
            Membership.join(user_id=admin, tenant_id=tenant_id, role=Role.ADMIN, now=now)
        )
        await repo.add(
            Membership.join(user_id=viewer, tenant_id=tenant_id, role=Role.VIEWER, now=now)
        )

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=owner)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        items, total = await repo.list_page(
            ListMembersQuery(tenant_id=tenant_id, roles=(Role.ADMIN, Role.VIEWER))
        )

    assert total == 2
    assert {it.role for it in items} == {Role.ADMIN, Role.VIEWER}


@pytest.mark.integration
async def test_list_page_sorts_display_name_desc(
    isolated_uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await _seed_tenant(isolated_uow)
    ana = await _seed_user_full(session_factory, display_name="Ana", email="ana@x")
    beto = await _seed_user_full(session_factory, display_name="Beto", email="beto@x")
    carla = await _seed_user_full(session_factory, display_name="Carla", email="carla@x")
    now = datetime.now(UTC)
    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=ana)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        await repo.add(Membership.create_owner(user_id=ana, tenant_id=tenant_id, now=now))
        await repo.add(
            Membership.join(user_id=beto, tenant_id=tenant_id, role=Role.VIEWER, now=now)
        )
        await repo.add(
            Membership.join(user_id=carla, tenant_id=tenant_id, role=Role.VIEWER, now=now)
        )

    async with isolated_uow.begin():
        await _set_guc(isolated_uow, tenant_id=tenant_id, user_id=ana)
        repo = MembershipRepositorySqlAlchemy(isolated_uow)
        items, total = await repo.list_page(
            ListMembersQuery(tenant_id=tenant_id, sort="display_name", dir="desc")
        )

    assert total == 3
    assert [it.display_name for it in items] == ["Carla", "Beto", "Ana"]
