"""Tenants outbound ports — Protocols satisfied by adapters."""

from __future__ import annotations

from contexts.tenants.application.ports.outbound.invitation_repository import (
    InvitationRepository,
)
from contexts.tenants.application.ports.outbound.invitation_token_generator import (
    InvitationTokenClaims,
    InvitationTokenGenerator,
    InvitationTokenIssued,
)
from contexts.tenants.application.ports.outbound.membership_repository import (
    MembershipRepository,
)
from contexts.tenants.application.ports.outbound.tenant_repository import (
    TenantRepository,
)

__all__ = [
    "InvitationRepository",
    "InvitationTokenClaims",
    "InvitationTokenGenerator",
    "InvitationTokenIssued",
    "MembershipRepository",
    "TenantRepository",
]
