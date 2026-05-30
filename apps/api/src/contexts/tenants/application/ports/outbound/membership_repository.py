"""``MembershipRepository`` outbound port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.tenants.domain import Membership


@runtime_checkable
class MembershipRepository(Protocol):
    async def add(self, membership: Membership) -> None: ...

    async def update(self, membership: Membership) -> None: ...

    async def find(self, *, user_id: UUID, tenant_id: UUID) -> Membership | None: ...

    async def list_by_tenant(self, tenant_id: UUID) -> list[Membership]: ...

    async def list_active_for_user(self, user_id: UUID) -> list[Membership]: ...


__all__ = ["MembershipRepository"]
