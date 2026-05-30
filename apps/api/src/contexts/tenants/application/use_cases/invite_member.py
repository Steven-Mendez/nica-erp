"""``InviteMember`` — issue a signed invitation token and email it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from contexts.identity.application.ports.outbound import EmailSender
from contexts.tenants.application.ports.outbound import (
    InvitationRepository,
    InvitationTokenGenerator,
    TenantRepository,
)
from contexts.tenants.domain import (
    Invitation,
    MemberInvited,
    Role,
    TenantNotFoundError,
)
from shared_kernel.application.outbox import OutboxWriter
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _render_email(*, tenant_name: str, invite_url: str) -> tuple[str, str, str]:
    subject = f"Invitation to {tenant_name} on nica-erp"
    text = (
        f"You have been invited to join {tenant_name} on nica-erp.\n\n"
        f"Accept here: {invite_url}\n\n"
        "This link expires in 7 days."
    )
    html = (
        f"<p>You have been invited to join <strong>{tenant_name}</strong> on nica-erp.</p>"
        f'<p><a href="{invite_url}">Accept the invitation</a> (expires in 7 days).</p>'
    )
    return subject, text, html


@dataclass(frozen=True, slots=True)
class InviteMemberCommand:
    tenant_id: UUID
    email: str
    proposed_role: str
    invite_url_template: str  # e.g. "https://app/invitations/accept#t={token}"


@dataclass(frozen=True, slots=True)
class InviteMemberResult:
    invitation_id: UUID
    expires_at: datetime


@dataclass(slots=True)
class InviteMember:
    uow: UnitOfWork
    tenant_repository: TenantRepository
    invitation_repository: InvitationRepository
    token_generator: InvitationTokenGenerator
    email_sender: EmailSender
    outbox: OutboxWriter
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: InviteMemberCommand) -> InviteMemberResult:
        role = Role.from_str(command.proposed_role)
        if role is Role.OWNER:
            raise ValueError("Cannot invite a new owner; use TransferOwnership (post-MVP)")
        now = self.now()
        issued = self.token_generator.mint(
            tenant_id=command.tenant_id,
            email=command.email,
            proposed_role=role,
            now=now,
        )
        invitation = Invitation.issue(
            tenant_id=command.tenant_id,
            email=command.email,
            proposed_role=role,
            token_hash=issued.token_hash,
            expires_at=issued.expires_at,
            now=now,
        )
        async with self.uow.begin():
            tenant = await self.tenant_repository.get(command.tenant_id)
            if tenant is None:
                raise TenantNotFoundError(str(command.tenant_id))
            await self.invitation_repository.add(invitation)
            await self.outbox.append(
                # Outbox primary key is the event_id. Cancelling and
                # re-inviting on the same ``invitation.id`` would
                # otherwise collide; ``aggregate_id`` keeps the
                # invitation id so consumers can still correlate.
                event_id=uuid4(),
                event_type="tenants.MemberInvited",
                event_version=1,
                aggregate_type="Invitation",
                aggregate_id=invitation.id,
                tenant_id=command.tenant_id,
                payload={
                    "tenant_id": str(command.tenant_id),
                    "invitation_id": str(invitation.id),
                    "email": invitation.email,
                    "proposed_role": invitation.proposed_role.value,
                    "invited_at": now.isoformat(),
                },
            )
            # MemberInvited as a Python event (unused for now — outbox
            # is the canonical surface).
            _ = MemberInvited(
                tenant_id=command.tenant_id,
                invitation_id=invitation.id,
                email=invitation.email,
                proposed_role=invitation.proposed_role.value,
                invited_at=now,
            )
        # Email is sent OUTSIDE the UoW so the SMTP/SES failure mode does
        # not roll the invitation back. If sending fails the operator
        # still has the invitation row and can re-send via a future
        # "resend invitation" use case (post-MVP); the link in the email
        # carries the plaintext token, which is already persisted as a
        # hash so the API can validate later.
        url = command.invite_url_template.format(token=issued.token)
        subject, text, html = _render_email(tenant_name=tenant.name, invite_url=url)
        await self.email_sender.send(to=invitation.email, subject=subject, html=html, text=text)
        return InviteMemberResult(invitation_id=invitation.id, expires_at=invitation.expires_at)


__all__ = ["InviteMember", "InviteMemberCommand", "InviteMemberResult"]
