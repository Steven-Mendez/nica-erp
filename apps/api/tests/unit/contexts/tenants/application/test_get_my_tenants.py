"""Unit tests for :class:`GetMyTenants`."""

from __future__ import annotations

from uuid import uuid4

from contexts.tenants.application.use_cases.get_my_tenants import GetMyTenants
from contexts.tenants.domain import Membership, Role


async def test_get_my_tenants_returns_views_for_active_memberships(
    fake_uow, membership_repo, seeded_tenant, fixed_now
) -> None:
    user_id = uuid4()
    owner = Membership.create_owner(user_id=user_id, tenant_id=seeded_tenant.id, now=fixed_now)
    await membership_repo.add(owner)

    uc = GetMyTenants(uow=fake_uow, membership_repository=membership_repo)
    views = await uc.execute(user_id=user_id)

    assert len(views) == 1
    assert views[0].tenant_id == seeded_tenant.id
    assert views[0].name == "Empresa A"
    assert views[0].role.value == "owner"


async def test_get_my_tenants_empty_when_no_memberships(fake_uow, membership_repo) -> None:
    uc = GetMyTenants(uow=fake_uow, membership_repository=membership_repo)
    views = await uc.execute(user_id=uuid4())
    assert views == []


async def test_get_my_tenants_skips_membership_with_missing_tenant(
    fake_uow, membership_repo, seeded_tenant, fixed_now
) -> None:
    """A membership whose tenant row is gone is dropped, not crashed on."""

    user_id = uuid4()
    await membership_repo.add(
        Membership.create_owner(user_id=user_id, tenant_id=seeded_tenant.id, now=fixed_now)
    )
    await membership_repo.add(
        Membership.join(user_id=user_id, tenant_id=uuid4(), role=Role.VIEWER, now=fixed_now)
    )

    uc = GetMyTenants(uow=fake_uow, membership_repository=membership_repo)
    views = await uc.execute(user_id=user_id)

    assert [v.tenant_id for v in views] == [seeded_tenant.id]
