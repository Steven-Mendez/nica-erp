"""Tenants domain: aggregates, VOs, events. Pure Python.

The ``domain-purity`` import-linter contract forbids ``sqlalchemy``,
``fastapi``, ``boto3`` imports and any cross-context import here.
"""

from __future__ import annotations

from contexts.tenants.domain.authorization_dgi import AuthorizationDgi
from contexts.tenants.domain.errors import (
    CannotDemoteOwnerError,
    CannotRemoveOwnerError,
    InvitationAlreadyAcceptedError,
    InvitationCancelledError,
    InvitationExpiredError,
    InvitationInvalidError,
    InvitationNotFoundError,
    NotAMemberError,
    OwnerAlreadyExistsError,
    OwnerRoleNotAllowedHereError,
    TenantNotFoundError,
)
from contexts.tenants.domain.events import (
    InvitationCancelled,
    MemberInvited,
    MemberJoined,
    MemberRemoved,
    MemberRoleChanged,
    TenantCreated,
)
from contexts.tenants.domain.invitation import Invitation
from contexts.tenants.domain.membership import Membership
from contexts.tenants.domain.municipality import KNOWN_MUNICIPALITIES, Municipality
from contexts.tenants.domain.regime import Regime
from contexts.tenants.domain.role import Role
from contexts.tenants.domain.ruc import Ruc
from contexts.tenants.domain.tenant import Tenant

__all__ = [
    "KNOWN_MUNICIPALITIES",
    "AuthorizationDgi",
    "CannotDemoteOwnerError",
    "CannotRemoveOwnerError",
    "Invitation",
    "InvitationAlreadyAcceptedError",
    "InvitationCancelled",
    "InvitationCancelledError",
    "InvitationExpiredError",
    "InvitationInvalidError",
    "InvitationNotFoundError",
    "MemberInvited",
    "MemberJoined",
    "MemberRemoved",
    "MemberRoleChanged",
    "Membership",
    "Municipality",
    "NotAMemberError",
    "OwnerAlreadyExistsError",
    "OwnerRoleNotAllowedHereError",
    "Regime",
    "Role",
    "Ruc",
    "Tenant",
    "TenantCreated",
    "TenantNotFoundError",
]
