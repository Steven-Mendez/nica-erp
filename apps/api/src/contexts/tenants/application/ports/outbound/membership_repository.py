"""``MembershipRepository`` outbound port."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

from contexts.tenants.domain import Membership

if TYPE_CHECKING:
    from contexts.tenants.application.use_cases.list_members import (
        ListMembersQuery,
        MemberView,
    )


@runtime_checkable
class MembershipRepository(Protocol):
    async def add(self, membership: Membership) -> None: ...

    async def update(self, membership: Membership) -> None: ...

    async def find(self, *, user_id: UUID, tenant_id: UUID) -> Membership | None: ...

    # deprecated: prefer ``list_page``; kept for callers that need every row.
    async def list_by_tenant(self, tenant_id: UUID) -> list[Membership]: ...

    async def list_active_for_user(self, user_id: UUID) -> list[Membership]: ...

    async def list_page(self, query: ListMembersQuery) -> tuple[list[MemberView], int]: ...


__all__ = ["MembershipRepository"]
