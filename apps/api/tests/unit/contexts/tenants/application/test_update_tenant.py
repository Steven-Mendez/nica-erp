"""Unit tests for :class:`UpdateTenant`."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.update_tenant import (
    UpdateTenant,
    UpdateTenantCommand,
)
from contexts.tenants.domain import AuthorizationDgi, TenantNotFoundError


async def test_update_tenant_applies_partial_changes(
    fake_uow, tenant_repo, seeded_tenant, fixed_now
) -> None:
    uc = UpdateTenant(uow=fake_uow, tenant_repository=tenant_repo, now=lambda: fixed_now)

    updated = await uc.execute(
        UpdateTenantCommand(tenant_id=seeded_tenant.id, name="New Name", is_withholder=True)
    )

    assert updated.name == "New Name"
    assert updated.is_withholder is True
    # Unchanged fields stay put.
    assert updated.municipality.value == "Managua"
    assert tenant_repo.update_count == 1


async def test_update_tenant_raises_when_missing(fake_uow, tenant_repo, fixed_now) -> None:
    uc = UpdateTenant(uow=fake_uow, tenant_repository=tenant_repo, now=lambda: fixed_now)

    with pytest.raises(TenantNotFoundError):
        await uc.execute(UpdateTenantCommand(tenant_id=uuid4(), name="Whatever"))


async def test_update_tenant_replaces_authorization_dgi(
    fake_uow, tenant_repo, seeded_tenant, fixed_now
) -> None:
    uc = UpdateTenant(uow=fake_uow, tenant_repository=tenant_repo, now=lambda: fixed_now)

    new_dgi = AuthorizationDgi(
        number="B-002",
        valid_from=date(2027, 1, 1),
        valid_to=date(2028, 1, 1),
    )

    updated = await uc.execute(
        UpdateTenantCommand(tenant_id=seeded_tenant.id, authorization_dgi=new_dgi)
    )

    assert updated.authorization_dgi.number == "B-002"
