"""RBAC catalog, ``Actor``, TTL cache, and ``ForbiddenError``.

This is shared kernel — no context imports allowed. The HTTP-layer
``require(*codes)`` dependency that consumes ``Actor`` lives in
``bootstrap.dependencies`` so the application layer never imports
FastAPI.
"""

from __future__ import annotations

from shared_kernel.permissions.actor import Actor
from shared_kernel.permissions.cache import PermissionCache
from shared_kernel.permissions.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLES,
    TENANT_PERMISSIONS,
    Permission,
)
from shared_kernel.permissions.errors import ForbiddenError

__all__ = [
    "DEFAULT_ROLE_PERMISSIONS",
    "ROLES",
    "TENANT_PERMISSIONS",
    "Actor",
    "ForbiddenError",
    "Permission",
    "PermissionCache",
]
