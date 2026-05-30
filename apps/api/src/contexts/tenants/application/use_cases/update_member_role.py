"""``UpdateMemberRole`` — change a member's role (not owner)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from contexts.tenants.application.ports.outbound import MembershipRepository
from contexts.tenants.domain import (
    CannotDemoteOwnerError,
    NotAMemberError,
    Role,
)
from shared_kernel.application.outbox import OutboxWriter
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class UpdateMemberRoleCommand:
    tenant_id: UUID
    target_user_id: UUID
    new_role: str


@dataclass(slots=True)
class UpdateMemberRole:
    uow: UnitOfWork
    membership_repository: MembershipRepository
    outbox: OutboxWriter
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: UpdateMemberRoleCommand) -> None:
        new_role = Role.from_str(command.new_role)
        if new_role is Role.OWNER:
            # Promoting to owner requires TransferOwnership (post-MVP).
            raise CannotDemoteOwnerError("Cannot promote to owner via update-role")
        now = self.now()
        async with self.uow.begin():
            membership = await self.membership_repository.find(
                user_id=command.target_user_id, tenant_id=command.tenant_id
            )
            if membership is None or membership.status != "active":
                raise NotAMemberError(str(command.target_user_id))
            if membership.role is Role.OWNER:
                raise CannotDemoteOwnerError(str(command.target_user_id))
            old_role = membership.role
            membership.change_role(new_role=new_role)
            await self.membership_repository.update(membership)
            await self.outbox.append(
                # Outbox primary key is the event_id. Two role changes on
                # the same ``membership.id`` would otherwise collide;
                # ``aggregate_id`` keeps the membership id so consumers
                # can still correlate.
                event_id=uuid4(),
                event_type="tenants.MemberRoleChanged",
                event_version=1,
                aggregate_type="Membership",
                aggregate_id=membership.id,
                tenant_id=command.tenant_id,
                payload={
                    "tenant_id": str(command.tenant_id),
                    "user_id": str(command.target_user_id),
                    "old_role": old_role.value,
                    "new_role": new_role.value,
                    "changed_at": now.isoformat(),
                },
            )


__all__ = ["UpdateMemberRole", "UpdateMemberRoleCommand"]
