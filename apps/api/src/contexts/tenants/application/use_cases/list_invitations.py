"""``ListInvitations`` — return pending invitations of a tenant."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.tenants.application.ports.outbound import InvitationRepository
from contexts.tenants.domain import Invitation
from shared_kernel.application.unit_of_work import UnitOfWork


@dataclass(slots=True)
class ListInvitations:
    uow: UnitOfWork
    invitation_repository: InvitationRepository

    async def execute(self, *, tenant_id: UUID) -> list[Invitation]:
        async with self.uow.begin():
            return await self.invitation_repository.list_by_tenant(tenant_id)


__all__ = ["ListInvitations"]
