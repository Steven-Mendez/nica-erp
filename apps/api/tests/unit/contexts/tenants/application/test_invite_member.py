"""Unit tests for :class:`InviteMember`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.invite_member import (
    InviteMember,
    InviteMemberCommand,
)
from contexts.tenants.domain import InvitationDuplicatePendingError, TenantNotFoundError


async def test_invite_member_persists_invitation_and_emits_outbox(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    seeded_tenant,
    fixed_now,
) -> None:
    uc = InviteMember(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    await uc.execute(
        InviteMemberCommand(
            tenant_id=seeded_tenant.id,
            email="invitee@test.dev",
            proposed_role="accountant",
            invite_url_template="https://localhost/invitations/accept#t={token}",
        )
    )

    assert invitation_repo.add_count == 1
    invitation = next(iter(invitation_repo.by_id.values()))
    assert invitation.email == "invitee@test.dev"
    assert invitation.proposed_role.value == "accountant"

    # Outbox row mirrors the new invitation.
    assert any(r["event_type"] == "tenants.MemberInvited" for r in outbox.rows)

    # Email is sent OUTSIDE the UoW; the recorder captures it.
    assert len(email_sender.sent) == 1
    sent = email_sender.sent[0]
    assert sent["to"] == "invitee@test.dev"
    # Audit F-024: subject + body are bilingual with Spanish first.
    assert sent["subject"].startswith("nica-erp: invitación a ")
    assert "/ invitation to " in sent["subject"]
    assert sent["text"].startswith("Invitación a ")
    assert "Has sido invitado a unirte" in sent["text"]
    assert "expira en 7 días" in sent["text"]
    # English block follows as secondary copy.
    assert "Invitation to " in sent["text"]
    assert "expires in 7 days" in sent["text"]


async def test_invite_member_rejects_owner_role(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    seeded_tenant,
    fixed_now,
) -> None:
    uc = InviteMember(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(ValueError):
        await uc.execute(
            InviteMemberCommand(
                tenant_id=seeded_tenant.id,
                email="x@test.dev",
                proposed_role="owner",
                invite_url_template="https://localhost/i/{token}",
            )
        )


async def test_invite_member_rejects_duplicate_pending_invitation(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    seeded_tenant,
    fixed_now,
) -> None:
    uc = InviteMember(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    await uc.execute(
        InviteMemberCommand(
            tenant_id=seeded_tenant.id,
            email="dupe@test.dev",
            proposed_role="viewer",
            invite_url_template="https://localhost/i/{token}",
        )
    )
    assert invitation_repo.add_count == 1
    sent_before = len(email_sender.sent)

    with pytest.raises(InvitationDuplicatePendingError):
        await uc.execute(
            InviteMemberCommand(
                tenant_id=seeded_tenant.id,
                email="DUPE@test.dev",  # case-insensitive match
                proposed_role="viewer",
                invite_url_template="https://localhost/i/{token}",
            )
        )
    # The second call MUST NOT persist a new invitation or send another email.
    assert invitation_repo.add_count == 1
    assert len(email_sender.sent) == sent_before


async def test_invite_member_raises_when_tenant_missing(
    fake_uow,
    tenant_repo,
    invitation_repo,
    token_generator,
    email_sender,
    outbox,
    fixed_now,
) -> None:
    uc = InviteMember(
        uow=fake_uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_generator,
        email_sender=email_sender,
        outbox=outbox,
        now=lambda: fixed_now,
    )

    with pytest.raises(TenantNotFoundError):
        await uc.execute(
            InviteMemberCommand(
                tenant_id=uuid4(),
                email="x@test.dev",
                proposed_role="viewer",
                invite_url_template="https://localhost/i/{token}",
            )
        )
