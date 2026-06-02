"""``InvitationRepository`` outbound port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.tenants.domain import Invitation


@runtime_checkable
class InvitationRepository(Protocol):
    async def add(self, invitation: Invitation) -> None: ...

    async def update(self, invitation: Invitation) -> None: ...

    async def get(self, invitation_id: UUID) -> Invitation | None: ...

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None: ...

    async def list_by_tenant(self, tenant_id: UUID) -> list[Invitation]: ...

    async def list_pending_by_email(self, tenant_id: UUID, email: str) -> list[Invitation]: ...


__all__ = ["InvitationRepository"]
