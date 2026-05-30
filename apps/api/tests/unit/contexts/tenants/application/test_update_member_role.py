"""Unit tests for :class:`UpdateMemberRole`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.update_member_role import (
    UpdateMemberRole,
    UpdateMemberRoleCommand,
)
from contexts.tenants.domain import (
    CannotDemoteOwnerError,
    Membership,
    NotAMemberError,
    Role,
)


async def test_update_member_role_changes_role_and_emits_outbox(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    target = uuid4()
    member = Membership.join(
        user_id=target,
        tenant_id=seeded_tenant.id,
        role=Role.VIEWER,
        now=fixed_now,
    )
    await membership_repo.add(member)

    uc = UpdateMemberRole(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    await uc.execute(
        UpdateMemberRoleCommand(
            tenant_id=seeded_tenant.id, target_user_id=target, new_role="accountant"
        )
    )

    updated = await membership_repo.find(user_id=target, tenant_id=seeded_tenant.id)
    assert updated is not None
    assert updated.role is Role.ACCOUNTANT

    event = next(r for r in outbox.rows if r["event_type"] == "tenants.MemberRoleChanged")
    assert event["payload"]["old_role"] == "viewer"
    assert event["payload"]["new_role"] == "accountant"


async def test_update_member_role_cannot_promote_to_owner(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    target = uuid4()
    member = Membership.join(
        user_id=target, tenant_id=seeded_tenant.id, role=Role.VIEWER, now=fixed_now
    )
    await membership_repo.add(member)

    uc = UpdateMemberRole(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(CannotDemoteOwnerError):
        await uc.execute(
            UpdateMemberRoleCommand(
                tenant_id=seeded_tenant.id, target_user_id=target, new_role="owner"
            )
        )


async def test_update_member_role_cannot_demote_owner(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    owner_id = uuid4()
    owner = Membership.create_owner(user_id=owner_id, tenant_id=seeded_tenant.id, now=fixed_now)
    await membership_repo.add(owner)

    uc = UpdateMemberRole(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(CannotDemoteOwnerError):
        await uc.execute(
            UpdateMemberRoleCommand(
                tenant_id=seeded_tenant.id, target_user_id=owner_id, new_role="admin"
            )
        )


async def test_update_member_role_not_a_member_raises(
    fake_uow, membership_repo, outbox, seeded_tenant, fixed_now
) -> None:
    uc = UpdateMemberRole(
        uow=fake_uow,
        membership_repository=membership_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(NotAMemberError):
        await uc.execute(
            UpdateMemberRoleCommand(
                tenant_id=seeded_tenant.id, target_user_id=uuid4(), new_role="admin"
            )
        )
