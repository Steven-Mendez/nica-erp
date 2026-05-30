"""``InvitationTokenGenerator`` outbound port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.tenants.domain import Role


@dataclass(frozen=True, slots=True)
class InvitationTokenIssued:
    token: str
    token_hash: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class InvitationTokenClaims:
    tenant_id: UUID
    email: str
    proposed_role: Role
    expires_at: datetime


@runtime_checkable
class InvitationTokenGenerator(Protocol):
    def mint(
        self,
        *,
        tenant_id: UUID,
        email: str,
        proposed_role: Role,
        now: datetime,
    ) -> InvitationTokenIssued: ...

    def verify(self, *, token: str) -> InvitationTokenClaims: ...

    def hash(self, *, token: str) -> str: ...


__all__ = [
    "InvitationTokenClaims",
    "InvitationTokenGenerator",
    "InvitationTokenIssued",
]
