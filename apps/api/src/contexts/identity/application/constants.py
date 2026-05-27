"""Application-layer constants for the identity context.

Kept in a leaf module so use cases can import the sentinel without creating
an import cycle through ``contexts.identity.application.__init__``.
"""

from __future__ import annotations

from uuid import UUID

# Sentinel tenant_id used on outbox rows whose events are tenant-agnostic
# (identity-context registration occurs before any tenant exists for the user).
SYSTEM_GLOBAL_TENANT_ID: UUID = UUID("00000000-0000-0000-0000-000000000000")


__all__ = ["SYSTEM_GLOBAL_TENANT_ID"]
