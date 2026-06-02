"""``ResendInvitation`` — cancel a pending invitation and issue a fresh one."""

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
    InvitationCancelled,
    InvitationNotFoundError,
    MemberInvited,
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
class ResendInvitationCommand:
    tenant_id: UUID
    invitation_id: UUID
    invite_url_template: str


@dataclass(frozen=True, slots=True)
class ResendInvitationResult:
    invitation_id: UUID
    expires_at: datetime


@dataclass(slots=True)
class ResendInvitation:
    uow: UnitOfWork
    tenant_repository: TenantRepository
    invitation_repository: InvitationRepository
    token_generator: InvitationTokenGenerator
    email_sender: EmailSender
    outbox: OutboxWriter
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: ResendInvitationCommand) -> ResendInvitationResult:
        now = self.now()
        async with self.uow.begin():
            tenant = await self.tenant_repository.get(command.tenant_id)
            if tenant is None:
                raise TenantNotFoundError(str(command.tenant_id))
            existing = await self.invitation_repository.get(command.invitation_id)
            if existing is None or existing.tenant_id != command.tenant_id:
                raise InvitationNotFoundError(str(command.invitation_id))
            # cancel() rejects already-accepted invitations; pending and
            # expired both flow through. Cancelling expired is the
            # cleanest reset before re-issuing.
            existing.cancel(now=now)
            await self.invitation_repository.update(existing)
            issued = self.token_generator.mint(
                tenant_id=existing.tenant_id,
                email=existing.email,
                proposed_role=existing.proposed_role,
                now=now,
            )
            replacement = Invitation.issue(
                tenant_id=existing.tenant_id,
                email=existing.email,
                proposed_role=existing.proposed_role,
                token_hash=issued.token_hash,
                expires_at=issued.expires_at,
                now=now,
            )
            await self.invitation_repository.add(replacement)
            await self.outbox.append(
                event_id=uuid4(),
                event_type="tenants.InvitationCancelled",
                event_version=1,
                aggregate_type="Invitation",
                aggregate_id=existing.id,
                tenant_id=command.tenant_id,
                payload={
                    "tenant_id": str(command.tenant_id),
                    "invitation_id": str(existing.id),
                    "cancelled_at": now.isoformat(),
                    "reason": "resend",
                },
            )
            await self.outbox.append(
                event_id=uuid4(),
                event_type="tenants.MemberInvited",
                event_version=1,
                aggregate_type="Invitation",
                aggregate_id=replacement.id,
                tenant_id=command.tenant_id,
                payload={
                    "tenant_id": str(command.tenant_id),
                    "invitation_id": str(replacement.id),
                    "email": replacement.email,
                    "proposed_role": replacement.proposed_role.value,
                    "invited_at": now.isoformat(),
                },
            )
            _ = InvitationCancelled(
                tenant_id=command.tenant_id,
                invitation_id=existing.id,
                cancelled_at=now,
            )
            _ = MemberInvited(
                tenant_id=command.tenant_id,
                invitation_id=replacement.id,
                email=replacement.email,
                proposed_role=replacement.proposed_role.value,
                invited_at=now,
            )
        url = command.invite_url_template.format(token=issued.token)
        subject, text, html = _render_email(tenant_name=tenant.name, invite_url=url)
        await self.email_sender.send(to=replacement.email, subject=subject, html=html, text=text)
        return ResendInvitationResult(
            invitation_id=replacement.id, expires_at=replacement.expires_at
        )


__all__ = ["ResendInvitation", "ResendInvitationCommand", "ResendInvitationResult"]
