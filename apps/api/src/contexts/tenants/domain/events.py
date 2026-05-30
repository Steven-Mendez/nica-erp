"""Versioned tenants domain events.

Event names emitted to the outbox carry the ``tenants.`` prefix:
``tenants.TenantCreated``, ``tenants.MemberInvited``, etc., all with
``event_version=1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class TenantCreated(DomainEvent):
    tenant_id: UUID
    name: str
    ruc: str | None
    municipality: str | None
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class MemberInvited(DomainEvent):
    tenant_id: UUID
    invitation_id: UUID
    email: str
    proposed_role: str
    invited_at: datetime


@dataclass(frozen=True, kw_only=True)
class MemberJoined(DomainEvent):
    tenant_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime


@dataclass(frozen=True, kw_only=True)
class MemberRemoved(DomainEvent):
    tenant_id: UUID
    user_id: UUID
    removed_at: datetime


@dataclass(frozen=True, kw_only=True)
class InvitationCancelled(DomainEvent):
    tenant_id: UUID
    invitation_id: UUID
    cancelled_at: datetime


@dataclass(frozen=True, kw_only=True)
class MemberRoleChanged(DomainEvent):
    tenant_id: UUID
    user_id: UUID
    old_role: str
    new_role: str
    changed_at: datetime


__all__ = [
    "InvitationCancelled",
    "MemberInvited",
    "MemberJoined",
    "MemberRemoved",
    "MemberRoleChanged",
    "TenantCreated",
]
