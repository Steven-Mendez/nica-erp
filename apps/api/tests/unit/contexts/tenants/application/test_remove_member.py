"""Unit tests for :class:`RemoveMember`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.remove_member import (
    RemoveMember,
    RemoveMemberCommand,
)
from contexts.tenants.domain import (
    CannotRemoveOwnerError,
    Membership,
    NotAMemberError,
    Role,
)


async def test_remove_member_soft_deletes_non_owner(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    target = uuid4()
    member = Membership.join(
        user_id=target,
        tenant_id=seeded_tenant.id,
        role=Role.ACCOUNTANT,
        now=fixed_now,
    )
    await membership_repo.add(member)

    uc = RemoveMember(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    await uc.execute(RemoveMemberCommand(tenant_id=seeded_tenant.id, target_user_id=target))

    updated = await membership_repo.find(user_id=target, tenant_id=seeded_tenant.id)
    assert updated is not None
    assert updated.status == "removed"
    assert any(r["event_type"] == "tenants.MemberRemoved" for r in outbox.rows)


async def test_remove_member_cannot_remove_owner(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    owner_id = uuid4()
    owner = Membership.create_owner(user_id=owner_id, tenant_id=seeded_tenant.id, now=fixed_now)
    await membership_repo.add(owner)

    uc = RemoveMember(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(CannotRemoveOwnerError):
        await uc.execute(RemoveMemberCommand(tenant_id=seeded_tenant.id, target_user_id=owner_id))


async def test_remove_member_not_a_member_raises(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    uc = RemoveMember(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(NotAMemberError):
        await uc.execute(RemoveMemberCommand(tenant_id=seeded_tenant.id, target_user_id=uuid4()))
