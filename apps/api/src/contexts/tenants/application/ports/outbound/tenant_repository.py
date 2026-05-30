"""``TenantRepository`` outbound port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.tenants.domain import Tenant


@runtime_checkable
class TenantRepository(Protocol):
    async def get(self, tenant_id: UUID) -> Tenant | None: ...

    async def get_by_ruc(self, ruc: str) -> Tenant | None: ...

    async def add(self, tenant: Tenant) -> None: ...

    async def update(self, tenant: Tenant) -> None: ...

    async def list_for_user(self, user_id: UUID) -> list[Tenant]: ...


__all__ = ["TenantRepository"]
