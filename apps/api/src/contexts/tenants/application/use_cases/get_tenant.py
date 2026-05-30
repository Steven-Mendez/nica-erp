"""``GetTenant`` — read-side fetch of a tenant aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.tenants.application.ports.outbound import TenantRepository
from contexts.tenants.domain import Tenant, TenantNotFoundError
from shared_kernel.application.unit_of_work import UnitOfWork


@dataclass(slots=True)
class GetTenant:
    uow: UnitOfWork
    tenant_repository: TenantRepository

    async def execute(self, *, tenant_id: UUID) -> Tenant:
        async with self.uow.begin():
            tenant = await self.tenant_repository.get(tenant_id)
            if tenant is None:
                raise TenantNotFoundError(str(tenant_id))
            return tenant


__all__ = ["GetTenant"]
