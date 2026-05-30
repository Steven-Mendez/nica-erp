"""Unit tests for :class:`AcceptInvitation`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.accept_invitation import (
    AcceptInvitation,
    AcceptInvitationCommand,
)
from contexts.tenants.domain import (
    Invitation,
    InvitationInvalidError,
    InvitationNotFoundError,
    Role,
)


async def test_accept_invitation_joins_user_and_emits_outbox(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    seeded_tenant,
    fixed_now,
) -> None:
    issued = token_generator.mint(
        tenant_id=seeded_tenant.id,
        email="invitee@test.dev",
        proposed_role=Role.ACCOUNTANT,
        now=fixed_now,
    )
    invitation = Invitation.issue(
        tenant_id=seeded_tenant.id,
        email="invitee@test.dev",
        proposed_role=Role.ACCOUNTANT,
        token_hash=issued.token_hash,
        expires_at=issued.expires_at,
        now=fixed_now,
    )
    await invitation_repo.add(invitation)

    uc = AcceptInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        membership_repository=membership_repo,
        token_generator=token_generator,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    invitee_id = uuid4()
    result = await uc.execute(AcceptInvitationCommand(token=issued.token, user_id=invitee_id))

    assert result.tenant_id == seeded_tenant.id
    assert result.role == "accountant"
    assert membership_repo.add_count == 1
    assert invitation_repo.update_count == 1
    assert any(r["event_type"] == "tenants.MemberJoined" for r in outbox.rows)


async def test_accept_invitation_unknown_token_raises(
    fake_uow, invitation_repo, membership_repo, token_generator, outbox, fixed_now
) -> None:
    uc = AcceptInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        membership_repository=membership_repo,
        token_generator=token_generator,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(InvitationNotFoundError):
        await uc.execute(AcceptInvitationCommand(token="no-such", user_id=uuid4()))


async def test_accept_invitation_verifier_failure_raises_invalid(
    fake_uow, invitation_repo, membership_repo, token_generator, outbox, fixed_now
) -> None:
    def boom(*, token: str) -> object:
        raise RuntimeError("signature failure")

    token_generator.verify = boom  # type: ignore[assignment]

    uc = AcceptInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        membership_repository=membership_repo,
        token_generator=token_generator,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(InvitationInvalidError):
        await uc.execute(AcceptInvitationCommand(token="anything", user_id=uuid4()))
