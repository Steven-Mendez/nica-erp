"""``Invitation`` entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from contexts.tenants.domain.errors import (
    InvitationAlreadyAcceptedError,
    InvitationCancelledError,
    InvitationExpiredError,
)
from contexts.tenants.domain.role import Role

InvitationStatus = Literal["pending", "accepted", "cancelled", "expired"]


@dataclass
class Invitation:
    id: UUID
    tenant_id: UUID
    email: str
    proposed_role: Role
    token_hash: str
    expires_at: datetime
    status: InvitationStatus
    cancelled_at: datetime | None
    created_at: datetime

    @classmethod
    def issue(
        cls,
        *,
        tenant_id: UUID,
        email: str,
        proposed_role: Role,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
        id_: UUID | None = None,
    ) -> Invitation:
        if proposed_role is Role.OWNER:
            raise ValueError("Cannot invite a new owner; transfer ownership instead")
        return cls(
            id=id_ or uuid4(),
            tenant_id=tenant_id,
            email=email.lower(),
            proposed_role=proposed_role,
            token_hash=token_hash,
            expires_at=expires_at,
            status="pending",
            cancelled_at=None,
            created_at=now,
        )

    def accept(self, *, now: datetime) -> None:
        if self.status == "accepted":
            raise InvitationAlreadyAcceptedError(f"Invitation {self.id} already accepted")
        if self.status == "cancelled":
            raise InvitationCancelledError(f"Invitation {self.id} was cancelled")
        if now > self.expires_at:
            raise InvitationExpiredError(f"Invitation {self.id} expired at {self.expires_at}")
        self.status = "accepted"

    def cancel(self, *, now: datetime) -> None:
        if self.status == "accepted":
            raise InvitationAlreadyAcceptedError(
                f"Invitation {self.id} already accepted; cannot cancel"
            )
        self.status = "cancelled"
        self.cancelled_at = now


__all__ = ["Invitation", "InvitationStatus"]
