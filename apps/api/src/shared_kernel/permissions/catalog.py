"""Canonical RBAC permission catalog.

This module is the **source of truth**: the Alembic migration that
seeds the ``permissions`` and ``role_permissions`` tables imports
these constants and writes them with ``ON CONFLICT DO NOTHING`` so
sprints 04-08 can extend the tuples and re-run without clearing.

The module MUST stay free of ``sqlalchemy``, ``fastapi``, and
``contexts.*`` imports — enforced by ``import-linter`` so the
catalog can be imported from a migration that runs before any
application wiring is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Permission:
    code: str
    resource: str
    action: str
    scope: Literal["own", "all", "na"]
    description: str


TENANT_PERMISSIONS: tuple[Permission, ...] = (
    Permission(
        code="tenant:read",
        resource="tenant",
        action="read",
        scope="na",
        description="View tenant fiscal metadata",
    ),
    Permission(
        code="tenant:write",
        resource="tenant",
        action="write",
        scope="na",
        description="Edit tenant fiscal metadata",
    ),
    Permission(
        code="members:read",
        resource="members",
        action="read",
        scope="na",
        description="List tenant members",
    ),
    Permission(
        code="members:invite",
        resource="members",
        action="invite",
        scope="na",
        description="Invite new members to the tenant",
    ),
    Permission(
        code="members:update-role",
        resource="members",
        action="update-role",
        scope="na",
        description="Change an existing member's role",
    ),
    Permission(
        code="members:remove",
        resource="members",
        action="remove",
        scope="na",
        description="Remove members from the tenant",
    ),
)


ROLES: tuple[str, ...] = ("viewer", "salesperson", "accountant", "admin", "owner")


DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"tenant:read"}),
    "salesperson": frozenset({"tenant:read"}),
    "accountant": frozenset({"tenant:read", "members:read"}),
    "admin": frozenset(
        {
            "tenant:read",
            "tenant:write",
            "members:read",
            "members:invite",
            "members:update-role",
            "members:remove",
        }
    ),
    "owner": frozenset(
        {
            "tenant:read",
            "tenant:write",
            "members:read",
            "members:invite",
            "members:update-role",
            "members:remove",
        }
    ),
}


__all__ = [
    "DEFAULT_ROLE_PERMISSIONS",
    "ROLES",
    "TENANT_PERMISSIONS",
    "Permission",
]
