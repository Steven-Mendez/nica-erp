"""Unit tests for :class:`CreateTenant`.

Uses the in-memory fakes from ``conftest.py`` so the test exercises
the use case's command-handling, owner-membership creation, and
``TenantCreated`` outbox emission without touching the database. The
``set_config('app.tenant_id', ...)`` branch the use case takes for
real SqlAlchemy UoWs is skipped here because :class:`FakeUow` does
not derive from :class:`SqlAlchemyUnitOfWork`.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.create_tenant import (
    CreateTenant,
    CreateTenantCommand,
)
from contexts.tenants.domain import AuthorizationDgi, Role


def _cmd(actor: str = "11111111-1111-1111-1111-111111111111") -> CreateTenantCommand:
    return CreateTenantCommand(
        actor_user_id=uuid4() if actor == "_random" else __import__("uuid").UUID(actor),
        name="Empresa A",
        ruc="0010101800010X",
        regime="general",
        municipality="Managua",
        authorization_dgi=AuthorizationDgi(
            number="A-001",
            valid_from=date(2026, 1, 1),
            valid_to=date(2027, 1, 1),
        ),
        fiscal_address="Rotonda Centroamérica, Managua",
        is_withholder=False,
    )


async def test_create_tenant_persists_tenant_owner_and_outbox(
    fake_uow, tenant_repo, membership_repo, outbox, fixed_now
) -> None:
    uc = CreateTenant(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    result = await uc.execute(_cmd())

    assert tenant_repo.add_count == 1
    assert membership_repo.add_count == 1
    assert fake_uow.committed is True

    # Owner membership belongs to the new tenant and the calling user.
    owner = membership_repo.rows[0]
    assert owner.role is Role.OWNER
    assert owner.status == "active"
    assert owner.tenant_id == result.tenant_id

    # Outbox carries TenantCreated.
    assert len(outbox.rows) == 1
    event = outbox.rows[0]
    assert event["event_type"] == "tenants.TenantCreated"
    assert event["tenant_id"] == result.tenant_id
    assert event["payload"]["name"] == "Empresa A"


async def test_create_tenant_rejects_malformed_ruc(
    fake_uow, tenant_repo, membership_repo, outbox, fixed_now
) -> None:
    uc = CreateTenant(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )
    cmd = CreateTenantCommand(
        actor_user_id=uuid4(),
        name="Empresa B",
        ruc="too-short",
        regime="general",
        municipality="Managua",
        authorization_dgi=AuthorizationDgi(
            number="A-001",
            valid_from=date(2026, 1, 1),
            valid_to=date(2027, 1, 1),
        ),
        fiscal_address="x",
        is_withholder=False,
    )

    with pytest.raises(ValueError):
        await uc.execute(cmd)

    # Domain validation runs BEFORE ``uow.begin()`` so the UoW never
    # opened; nothing was persisted.
    assert tenant_repo.add_count == 0
    assert membership_repo.add_count == 0
    assert outbox.rows == []
