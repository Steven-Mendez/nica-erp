"""Unit tests for :class:`AcceptInvitation`."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from contexts.tenants.application.use_cases.accept_invitation import (
    AcceptInvitation,
    AcceptInvitationCommand,
)
from contexts.tenants.domain import (
    Invitation,
    InvitationIdentityMismatchError,
    InvitationInvalidError,
    InvitationNotFoundError,
    Role,
)


def _baseline_command(
    *,
    token: str,
    user_id: UUID,
    user_email: str = "invitee@test.dev",
    prior_active_tenant: str | None = None,
    refresh_token: str | None = None,
) -> AcceptInvitationCommand:
    return AcceptInvitationCommand(
        token=token,
        user_id=user_id,
        user_email=user_email,
        external_sub=f"sub-{user_id}",
        prior_active_tenant=prior_active_tenant,
        refresh_token=refresh_token,
    )


async def test_accept_invitation_joins_user_and_emits_outbox(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    invitee_id = uuid4()
    result = await uc.execute(_baseline_command(token=issued.token, user_id=invitee_id))

    assert result.tenant_id == seeded_tenant.id
    assert result.role == "accountant"
    assert result.tokens is None  # no refresh_token supplied → no rotation
    assert membership_repo.add_count == 1
    assert invitation_repo.update_count == 1
    assert any(r["event_type"] == "tenants.MemberJoined" for r in outbox.rows)
    assert identity_provider.update_active_tenant_calls == []


async def test_accept_invitation_unknown_token_raises(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
    fixed_now,
) -> None:
    uc = AcceptInvitation(
        uow=fake_uow,
        invitation_repository=invitation_repo,
        membership_repository=membership_repo,
        token_generator=token_generator,
        outbox=outbox,
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    with pytest.raises(InvitationNotFoundError):
        await uc.execute(_baseline_command(token="no-such", user_id=uuid4()))


async def test_accept_invitation_verifier_failure_raises_invalid(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
    fixed_now,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    with pytest.raises(InvitationInvalidError):
        await uc.execute(_baseline_command(token="anything", user_id=uuid4()))


async def test_first_membership_with_refresh_token_rotates_session(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    invitee_id = uuid4()
    result = await uc.execute(
        _baseline_command(
            token=issued.token,
            user_id=invitee_id,
            prior_active_tenant=None,
            refresh_token="current-refresh",
        )
    )

    assert result.tokens is not None
    assert result.tokens.access_token == identity_provider.access_token_value
    assert result.tokens.refresh_token == identity_provider.refresh_token_value
    assert identity_provider.update_active_tenant_calls == [
        (f"sub-{invitee_id}", str(seeded_tenant.id))
    ]


async def test_veteran_caller_skips_rotation(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    invitee_id = uuid4()
    result = await uc.execute(
        _baseline_command(
            token=issued.token,
            user_id=invitee_id,
            prior_active_tenant="other-empresa-uuid",
            refresh_token="current-refresh",
        )
    )

    assert result.tokens is None
    assert identity_provider.update_active_tenant_calls == []


async def test_first_membership_without_refresh_token_skips_rotation(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    result = await uc.execute(
        _baseline_command(
            token=issued.token,
            user_id=uuid4(),
            prior_active_tenant=None,
            refresh_token=None,
        )
    )

    assert result.tokens is None
    assert identity_provider.update_active_tenant_calls == []


async def test_accept_invitation_identity_mismatch_is_noop(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    with pytest.raises(InvitationIdentityMismatchError):
        await uc.execute(
            _baseline_command(
                token=issued.token,
                user_id=uuid4(),
                user_email="someone-else@test.dev",
            )
        )

    assert membership_repo.add_count == 0
    assert invitation_repo.update_count == 0
    assert outbox.rows == []


async def test_accept_invitation_email_compare_is_case_insensitive(
    fake_uow,
    invitation_repo,
    membership_repo,
    token_generator,
    outbox,
    identity_provider,
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
        identity_provider=identity_provider,
        now=lambda: fixed_now,
    )

    result = await uc.execute(
        _baseline_command(
            token=issued.token,
            user_id=uuid4(),
            user_email="INVITEE@test.dev",
        )
    )

    assert result.tenant_id == seeded_tenant.id
    assert membership_repo.add_count == 1
