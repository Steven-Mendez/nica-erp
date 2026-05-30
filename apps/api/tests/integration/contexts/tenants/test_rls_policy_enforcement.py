"""Direct RLS-policy enforcement guard.

The existing e2e ``test_rls_tenant_isolation.py`` proves the HTTP layer
honours the tenant claim. This integration test proves the *Postgres
policy itself* enforces the per-tenant filter when the HTTP middleware
is absent. If a future migration drops ``FORCE ROW LEVEL SECURITY``,
flips ``nica_erp_app`` to ``BYPASSRLS``, or rewrites the policy body
in a way that admits cross-tenant rows, this test fails before the
e2e test would even notice.

The session factory authenticates as ``nica_erp_app`` (NOBYPASSRLS) —
the same role production runs as — so the policy applies exactly as
it would in production.

Worked example of ``tests/_factories/tenants`` consumption.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests._factories.tenants import (
    seed_invitation_row,
    seed_membership_row,
    seed_tenant_row,
    seed_user_row,
)

pytestmark = pytest.mark.integration


async def _set_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """Set ``app.tenant_id`` for the current transaction.

    The policy bodies cast the GUC value to ``uuid``; setting it to the
    empty string would trip ``invalid input syntax for type uuid: ""``
    the next time the policy runs. To represent the "no tenant active"
    state, production uses the zero-UUID sentinel
    (see ``bootstrap/container.py._ZERO_UUID``).
    """

    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"),
        {"t": str(tenant_id)},
    )


@pytest.fixture
async def _truncate(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE invitations RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE tenant_members RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE tenants RESTART IDENTITY CASCADE"))
        await session.commit()


async def test_rls_filters_tenant_members_per_tenant(
    session_factory: async_sessionmaker[AsyncSession],
    _truncate: None,
) -> None:
    tenant_a, tenant_b = uuid4(), uuid4()

    async with session_factory() as session:
        await seed_tenant_row(session, id_=tenant_a, name="A")
        await seed_tenant_row(session, id_=tenant_b, name="B")
        user_a = await seed_user_row(session, email="alice@a.example")
        user_b = await seed_user_row(session, email="bob@b.example")
        member_a = await seed_membership_row(session, tenant_id=tenant_a, user_id=user_a)
        member_b = await seed_membership_row(session, tenant_id=tenant_b, user_id=user_b)
        await session.commit()

    async with session_factory() as session:
        await _set_tenant(session, tenant_b)
        rows = (await session.execute(text("SELECT id FROM tenant_members"))).all()
        assert {row[0] for row in rows} == {member_b}, (
            "RLS leak: nica_erp_app saw a tenant_members row outside tenant B"
        )

    async with session_factory() as session:
        await _set_tenant(session, tenant_a)
        rows = (await session.execute(text("SELECT id FROM tenant_members"))).all()
        assert {row[0] for row in rows} == {member_a}


async def test_rls_filters_invitations_per_tenant(
    session_factory: async_sessionmaker[AsyncSession],
    _truncate: None,
) -> None:
    tenant_a, tenant_b = uuid4(), uuid4()

    async with session_factory() as session:
        await seed_tenant_row(session, id_=tenant_a, name="A")
        await seed_tenant_row(session, id_=tenant_b, name="B")
        inv_a = await seed_invitation_row(session, tenant_id=tenant_a, email="a@x.example")
        inv_b = await seed_invitation_row(session, tenant_id=tenant_b, email="b@x.example")
        await session.commit()

    async with session_factory() as session:
        await _set_tenant(session, tenant_b)
        rows = (await session.execute(text("SELECT id FROM invitations"))).all()
        assert {row[0] for row in rows} == {inv_b}

    async with session_factory() as session:
        await _set_tenant(session, tenant_a)
        rows = (await session.execute(text("SELECT id FROM invitations"))).all()
        assert {row[0] for row in rows} == {inv_a}


async def test_rls_hides_everything_when_tenant_id_is_zero_sentinel(
    session_factory: async_sessionmaker[AsyncSession],
    _truncate: None,
) -> None:
    """Production uses the zero-UUID sentinel as the 'no tenant active'
    value (see ``bootstrap/container.py._ZERO_UUID``). The policy compares
    ``tenant_id = '00…'::uuid`` and hides every real row. If that breaks
    — e.g. a future contributor seeds a row with the zero UUID — the
    safety net is gone.
    """

    tenant_id = uuid4()
    zero_uuid = UUID("00000000-0000-0000-0000-000000000000")

    async with session_factory() as session:
        await seed_tenant_row(session, id_=tenant_id, name="X")
        await seed_invitation_row(session, tenant_id=tenant_id, email="x@x.example")
        await session.commit()

    async with session_factory() as session:
        await _set_tenant(session, zero_uuid)
        rows = (await session.execute(text("SELECT id FROM invitations"))).all()
        assert rows == [], (
            "RLS leak: with app.tenant_id set to the zero-UUID sentinel, "
            "invitations should be invisible — found rows"
        )


async def test_app_role_is_nobypassrls(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Posture sanity: if someone flips nica_erp_app to BYPASSRLS, fail."""

    async with session_factory() as session:
        bypass = (
            await session.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'nica_erp_app'")
            )
        ).scalar_one()
        assert bypass is False, (
            "Posture regression: nica_erp_app has BYPASSRLS — every RLS test "
            "would silently pass. Revert the migration that flipped this."
        )
