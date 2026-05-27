"""Domain events emitted by the identity context.

Event-type strings are stable contract identifiers consumed by the outbox
publisher; the module-level constants are the canonical source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.domain.events import DomainEvent

IDENTITY_USER_REGISTERED_EVENT_TYPE = "identity.UserRegistered"
IDENTITY_USER_REGISTERED_EVENT_VERSION = 1

IDENTITY_PASSWORD_RESET_EVENT_TYPE = "identity.PasswordReset"
IDENTITY_PASSWORD_RESET_EVENT_VERSION = 1


@dataclass(frozen=True, kw_only=True)
class UserRegistered(DomainEvent):
    user_id: UUID
    email: str
    registered_at: datetime


@dataclass(frozen=True, kw_only=True)
class PasswordReset(DomainEvent):
    user_id: UUID
    reset_at: datetime


__all__ = [
    "IDENTITY_PASSWORD_RESET_EVENT_TYPE",
    "IDENTITY_PASSWORD_RESET_EVENT_VERSION",
    "IDENTITY_USER_REGISTERED_EVENT_TYPE",
    "IDENTITY_USER_REGISTERED_EVENT_VERSION",
    "PasswordReset",
    "UserRegistered",
]
