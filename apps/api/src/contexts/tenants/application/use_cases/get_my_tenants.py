"""``GetMyTenants`` — list memberships of the current user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.tenants.application.ports.outbound import MembershipRepository
from contexts.tenants.domain import Role
from shared_kernel.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class MyTenantView:
    tenant_id: UUID
    name: str
    role: Role
    status: str
    joined_at: datetime


@dataclass(slots=True)
class GetMyTenants:
    uow: UnitOfWork
    membership_repository: MembershipRepository

    async def execute(self, *, user_id: UUID) -> list[MyTenantView]:
        # Single JOIN instead of one tenant lookup per membership: the
        # repository resolves membership + tenant in one round trip and
        # skips memberships whose tenant row is missing (an orphan there
        # is a data bug, not a security boundary — tenants has no RLS).
        async with self.uow.begin():
            return await self.membership_repository.list_active_with_tenant_for_user(user_id)


__all__ = ["GetMyTenants", "MyTenantView"]
