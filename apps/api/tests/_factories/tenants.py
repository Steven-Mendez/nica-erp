"""Tenants-context domain object builders and DB row seeders.

The aggregate builder returns a fully-valid ``Tenant`` constructed via
``Tenant.register`` so the ``TenantCreated`` event lands in
``pop_events()``. The row seeders bypass the aggregate and write straight
through a session — useful when the test needs a row to exist but does
not care about the in-Python aggregate.

The seeders set ``app.tenant_id`` to the row's own ``tenant_id`` before
the INSERT so the RLS ``WITH CHECK`` policy passes (the conftest
session_factory authenticates as ``nica_erp_app``, which is
NOBYPASSRLS).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from contexts.tenants.domain import (
    AuthorizationDgi,
    Invitation,
    Membership,
    Municipality,
    Regime,
    Role,
    Ruc,
    Tenant,
)


def make_tenant(
    *,
    id_: UUID | None = None,
    name: str = "Empresa Demo",
    ruc: str = "0010101800010X",
    regime: str = "general",
    municipality: str = "Managua",
    is_withholder: bool = False,
    now: datetime | None = None,
) -> Tenant:
    """Return a ``Tenant`` aggregate ready for unit tests."""

    moment = now or datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    return Tenant.register(
        name=name,
        ruc=Ruc.parse(ruc),
        regime=Regime(regime),  # type: ignore[arg-type]
        municipality=Municipality(municipality),
        authorization_dgi=AuthorizationDgi(
            number="A-001",
            valid_from=date(moment.year, 1, 1),
            valid_to=date(moment.year + 1, 1, 1),
        ),
        fiscal_address="Rotonda Centroamérica, Managua",
        is_withholder=is_withholder,
        now=moment,
        id_=id_ or uuid4(),
    )


def make_membership(
    *,
    user_id: UUID | None = None,
    tenant_id: UUID | None = None,
    role: Role = Role.VIEWER,
    now: datetime | None = None,
) -> Membership:
    """Return a ``Membership`` constructed via ``join`` (no owner).

    Owners must come through ``Membership.create_owner`` by domain rule;
    use that directly when you need one.
    """

    moment = now or datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    return Membership.join(
        user_id=user_id or uuid4(),
        tenant_id=tenant_id or uuid4(),
        role=role,
        now=moment,
    )


def make_invitation(
    *,
    tenant_id: UUID | None = None,
    email: str = "invitee@nica-erp.test",
    proposed_role: Role = Role.VIEWER,
    now: datetime | None = None,
    ttl: timedelta = timedelta(days=7),
) -> Invitation:
    """Return a pending ``Invitation`` issued via ``Invitation.issue``."""

    moment = now or datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    return Invitation.issue(
        tenant_id=tenant_id or uuid4(),
        email=email,
        proposed_role=proposed_role,
        token_hash=f"hash-{email}",
        expires_at=moment + ttl,
        now=moment,
    )


async def seed_tenant_row(
    session: AsyncSession,
    *,
    id_: UUID | None = None,
    name: str = "Empresa Demo",
    now: datetime | None = None,
) -> UUID:
    """Insert a minimal ``tenants`` row and return its id.

    The ``tenants`` table itself is not under RLS — only ``tenant_members``
    and ``invitations`` are. The caller is responsible for the commit.
    """

    tenant_id = id_ or uuid4()
    moment = now or datetime.now(UTC)
    await session.execute(
        text(
            "INSERT INTO tenants (id, name, status, is_withholder, created_at, updated_at) "
            "VALUES (:id, :name, 'active', false, :now, :now)"
        ),
        {"id": tenant_id, "name": name, "now": moment},
    )
    return tenant_id


async def seed_user_row(
    session: AsyncSession,
    *,
    id_: UUID | None = None,
    email: str | None = None,
) -> UUID:
    """Insert a ``users`` row (for FK targets) and return its id."""

    user_id = id_ or uuid4()
    await session.execute(
        text("INSERT INTO users (id, external_sub, email) VALUES (:id, :sub, :email)"),
        {
            "id": user_id,
            "sub": str(user_id),
            "email": email or f"{user_id}@nica-erp.test",
        },
    )
    return user_id


async def seed_membership_row(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    role: str = "admin",
    id_: UUID | None = None,
    now: datetime | None = None,
) -> UUID:
    """Insert a ``tenant_members`` row under the matching ``app.tenant_id``.

    The RLS ``WITH CHECK`` policy compares ``tenant_id`` against
    ``current_setting('app.tenant_id', true)::uuid``; the seeder sets it
    explicitly so the INSERT passes. The caller is responsible for the
    commit.
    """

    membership_id = id_ or uuid4()
    moment = now or datetime.now(UTC)
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"),
        {"t": str(tenant_id)},
    )
    await session.execute(
        text(
            "INSERT INTO tenant_members "
            "(id, user_id, tenant_id, role, status, joined_at) "
            "VALUES (:id, :user_id, :tenant_id, :role, 'active', :now)"
        ),
        {
            "id": membership_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "now": moment,
        },
    )
    return membership_id


async def seed_invitation_row(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    email: str,
    proposed_role: str = "viewer",
    id_: UUID | None = None,
    now: datetime | None = None,
    ttl: timedelta = timedelta(days=7),
) -> UUID:
    """Insert an ``invitations`` row under the matching ``app.tenant_id``."""

    invitation_id = id_ or uuid4()
    moment = now or datetime.now(UTC)
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"),
        {"t": str(tenant_id)},
    )
    await session.execute(
        text(
            "INSERT INTO invitations "
            "(id, tenant_id, email, proposed_role, token_hash, expires_at, "
            "status, created_at) "
            "VALUES (:id, :tenant_id, :email, :role, :hash, :exp, 'pending', :now)"
        ),
        {
            "id": invitation_id,
            "tenant_id": tenant_id,
            "email": email,
            "role": proposed_role,
            "hash": f"h-{invitation_id}",
            "exp": moment + ttl,
            "now": moment,
        },
    )
    return invitation_id


__all__ = [
    "Role",
    "make_invitation",
    "make_membership",
    "make_tenant",
    "seed_invitation_row",
    "seed_membership_row",
    "seed_tenant_row",
    "seed_user_row",
]
