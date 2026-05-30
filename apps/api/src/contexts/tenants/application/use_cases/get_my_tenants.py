"""``GetMyTenants`` — list memberships of the current user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.tenants.application.ports.outbound import (
    MembershipRepository,
    TenantRepository,
)
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
    tenant_repository: TenantRepository

    async def execute(self, *, user_id: UUID) -> list[MyTenantView]:
        async with self.uow.begin():
            memberships = await self.membership_repository.list_active_for_user(user_id)
            views: list[MyTenantView] = []
            for m in memberships:
                tenant = await self.tenant_repository.get(m.tenant_id)
                if tenant is None:
                    # Membership references a tenant the current GUC can see
                    # via tenant_members_self, but the tenants table has no
                    # RLS; an orphan row here would indicate a data bug, not
                    # a security boundary. Skip rather than crash the picker.
                    continue
                views.append(
                    MyTenantView(
                        tenant_id=tenant.id,
                        name=tenant.name,
                        role=m.role,
                        status=tenant.status,
                        joined_at=m.joined_at,
                    )
                )
            return views


__all__ = ["GetMyTenants", "MyTenantView"]
