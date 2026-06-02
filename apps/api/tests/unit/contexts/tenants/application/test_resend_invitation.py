"""Unit tests for :class:`ResendInvitation`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.invite_member import (
    InviteMember,
    InviteMemberCommand,
)
from contexts.tenants.application.use_cases.resend_invitation import (
    ResendInvitation,
    ResendInvitationCommand,
)
from contexts.tenants.domain import (
    InvitationNotFoundError,
    TenantNotFoundError,
)


async def test_resend_cancels_existing_and_issues_a_fresh_invitation(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    seeded_tenant,
    fixed_now,
) -> None:
    invite = InviteMember(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )
    await invite.execute(
        InviteMemberCommand(
            tenant_id=seeded_tenant.id,
            email="resend@test.dev",
            proposed_role="viewer",
            invite_url_template="https://localhost/i/{token}",
        )
    )
    original = next(iter(invitation_repo.by_id.values()))
    sent_before = len(email_sender.sent)

    resend = ResendInvitation(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )
    result = await resend.execute(
        ResendInvitationCommand(
            tenant_id=seeded_tenant.id,
            invitation_id=original.id,
            invite_url_template="https://localhost/i/{token}",
        )
    )

    # Original was cancelled, replacement is pending.
    assert invitation_repo.by_id[original.id].status == "cancelled"
    assert invitation_repo.by_id[original.id].cancelled_at == fixed_now
    replacement = invitation_repo.by_id[result.invitation_id]
    assert replacement.id != original.id
    assert replacement.email == "resend@test.dev"
    assert replacement.proposed_role == original.proposed_role
    assert replacement.status == "pending"
    # A fresh email was dispatched.
    assert len(email_sender.sent) == sent_before + 1
    # Two outbox events emitted on resend: cancellation + new invitation.
    types = [r["event_type"] for r in outbox.rows]
    assert types.count("tenants.InvitationCancelled") >= 1
    assert types.count("tenants.MemberInvited") >= 2


async def test_resend_raises_when_invitation_missing(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    seeded_tenant,
    fixed_now,
) -> None:
    resend = ResendInvitation(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )
    with pytest.raises(InvitationNotFoundError):
        await resend.execute(
            ResendInvitationCommand(
                tenant_id=seeded_tenant.id,
                invitation_id=uuid4(),
                invite_url_template="https://localhost/i/{token}",
            )
        )


async def test_resend_raises_when_tenant_missing(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    fixed_now,
) -> None:
    resend = ResendInvitation(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )
    with pytest.raises(TenantNotFoundError):
        await resend.execute(
            ResendInvitationCommand(
                tenant_id=uuid4(),
                invitation_id=uuid4(),
                invite_url_template="https://localhost/i/{token}",
            )
        )
