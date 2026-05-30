"""Unit tests for :class:`SwitchActiveTenant`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.switch_active_tenant import (
    SwitchActiveTenant,
    SwitchActiveTenantCommand,
)
from contexts.tenants.domain import Membership, NotAMemberError


async def test_switch_active_tenant_updates_idp_and_refreshes_tokens(
    fake_uow, membership_repo, identity_provider, seeded_tenant, fixed_now
) -> None:
    user_id = uuid4()
    membership = Membership.create_owner(user_id=user_id, tenant_id=seeded_tenant.id, now=fixed_now)
    await membership_repo.add(membership)

    uc = SwitchActiveTenant(
        uow=fake_uow,
        membership_repository=membership_repo,
        identity_provider=identity_provider,
    )

    identity = await uc.execute(
        SwitchActiveTenantCommand(
            actor_user_id=user_id,
            external_sub=str(user_id),
            target_tenant_id=seeded_tenant.id,
            refresh_token="old-refresh",
        )
    )

    assert identity.access_token == identity_provider.access_token_value
    assert identity_provider.update_active_tenant_calls == [(str(user_id), str(seeded_tenant.id))]


async def test_switch_active_tenant_rejects_non_member(
    fake_uow, membership_repo, identity_provider, seeded_tenant
) -> None:
    uc = SwitchActiveTenant(
        uow=fake_uow,
        membership_repository=membership_repo,
        identity_provider=identity_provider,
    )

    with pytest.raises(NotAMemberError):
        await uc.execute(
            SwitchActiveTenantCommand(
                actor_user_id=uuid4(),
                external_sub=str(uuid4()),
                target_tenant_id=seeded_tenant.id,
                refresh_token="r",
            )
        )

    # Side-effect on the identity provider only fires when membership exists.
    assert identity_provider.update_active_tenant_calls == []
