"""Unit tests for :class:`GetTenant`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.get_tenant import GetTenant
from contexts.tenants.domain import TenantNotFoundError


async def test_get_tenant_returns_aggregate(fake_uow, tenant_repo, seeded_tenant) -> None:
    uc = GetTenant(uow=fake_uow, tenant_repository=tenant_repo)
    found = await uc.execute(tenant_id=seeded_tenant.id)
    assert found.id == seeded_tenant.id
    assert found.name == "Empresa A"


async def test_get_tenant_raises_when_missing(fake_uow, tenant_repo) -> None:
    uc = GetTenant(uow=fake_uow, tenant_repository=tenant_repo)
    with pytest.raises(TenantNotFoundError):
        await uc.execute(tenant_id=uuid4())
