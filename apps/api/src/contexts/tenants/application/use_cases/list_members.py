"""``ListMembers`` — return active and removed memberships of a tenant."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.tenants.application.ports.outbound import MembershipRepository
from contexts.tenants.domain import Membership
from shared_kernel.application.unit_of_work import UnitOfWork


@dataclass(slots=True)
class ListMembers:
    uow: UnitOfWork
    membership_repository: MembershipRepository

    async def execute(self, *, tenant_id: UUID) -> list[Membership]:
        async with self.uow.begin():
            return await self.membership_repository.list_by_tenant(tenant_id)


__all__ = ["ListMembers"]
