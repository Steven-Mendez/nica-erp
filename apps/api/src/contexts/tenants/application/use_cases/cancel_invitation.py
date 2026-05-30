"""``CancelInvitation`` — admins cancel pending invitations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from contexts.tenants.application.ports.outbound import InvitationRepository
from contexts.tenants.domain import InvitationNotFoundError
from shared_kernel.application.outbox import OutboxWriter
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CancelInvitationCommand:
    tenant_id: UUID
    invitation_id: UUID


@dataclass(slots=True)
class CancelInvitation:
    uow: UnitOfWork
    invitation_repository: InvitationRepository
    outbox: OutboxWriter
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: CancelInvitationCommand) -> None:
        now = self.now()
        async with self.uow.begin():
            invitation = await self.invitation_repository.get(command.invitation_id)
            if invitation is None or invitation.tenant_id != command.tenant_id:
                # RLS guarantees the second condition is redundant for foreign
                # tenants, but the check is cheap and defends against logic
                # drift in future repository changes.
                raise InvitationNotFoundError(str(command.invitation_id))
            invitation.cancel(now=now)
            await self.invitation_repository.update(invitation)
            await self.outbox.append(
                # Distinct UUID per event — ``invitation.id`` is the
                # outbox row's ``aggregate_id``, not its primary key.
                # Using the invitation id directly collides with the
                # ``tenants.MemberInvited`` row written by the
                # ``InviteMember`` use case for the same invitation.
                event_id=uuid4(),
                event_type="tenants.InvitationCancelled",
                event_version=1,
                aggregate_type="Invitation",
                aggregate_id=invitation.id,
                tenant_id=command.tenant_id,
                payload={
                    "tenant_id": str(command.tenant_id),
                    "invitation_id": str(invitation.id),
                    "cancelled_at": now.isoformat(),
                },
            )


__all__ = ["CancelInvitation", "CancelInvitationCommand"]
