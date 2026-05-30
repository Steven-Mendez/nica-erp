"""Unit tests for :class:`CancelInvitation`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.cancel_invitation import (
    CancelInvitation,
    CancelInvitationCommand,
)
from contexts.tenants.domain import Invitation, InvitationNotFoundError, Role


async def test_cancel_invitation_marks_cancelled_and_emits_outbox(
    fake_uow, invitation_repo, token_generator, outbox, seeded_tenant, fixed_now
) -> None:
    issued = token_generator.mint(
        tenant_id=seeded_tenant.id,
        email="invitee@test.dev",
        proposed_role=Role.VIEWER,
        now=fixed_now,
    )
    invitation = Invitation.issue(
        tenant_id=seeded_tenant.id,
        email="invitee@test.dev",
        proposed_role=Role.VIEWER,
        token_hash=issued.token_hash,
        expires_at=issued.expires_at,
        now=fixed_now,
    )
    await invitation_repo.add(invitation)

    uc = CancelInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    await uc.execute(
        CancelInvitationCommand(tenant_id=seeded_tenant.id, invitation_id=invitation.id)
    )

    updated = invitation_repo.by_id[invitation.id]
    assert updated.status == "cancelled"
    assert any(r["event_type"] == "tenants.InvitationCancelled" for r in outbox.rows)


async def test_cancel_invitation_unknown_id_raises(
    fake_uow, invitation_repo, outbox, fixed_now
) -> None:
    uc = CancelInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(InvitationNotFoundError):
        await uc.execute(CancelInvitationCommand(tenant_id=uuid4(), invitation_id=uuid4()))


async def test_cancel_invitation_cross_tenant_id_raises(
    fake_uow, invitation_repo, token_generator, outbox, seeded_tenant, fixed_now
) -> None:
    """Defense-in-depth: even if RLS leaked a row, the use case rejects mismatched tenant_id."""

    issued = token_generator.mint(
        tenant_id=seeded_tenant.id,
        email="a@test.dev",
        proposed_role=Role.VIEWER,
        now=fixed_now,
    )
    invitation = Invitation.issue(
        tenant_id=seeded_tenant.id,
        email="a@test.dev",
        proposed_role=Role.VIEWER,
        token_hash=issued.token_hash,
        expires_at=issued.expires_at,
        now=fixed_now,
    )
    await invitation_repo.add(invitation)

    uc = CancelInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    other_tenant = uuid4()
    with pytest.raises(InvitationNotFoundError):
        await uc.execute(
            CancelInvitationCommand(tenant_id=other_tenant, invitation_id=invitation.id)
        )
