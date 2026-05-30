"""Request-scoped authorization context (``Actor``).

The HTTP layer materialises one ``Actor`` per request via the
``current_actor`` dependency in ``bootstrap.dependencies``. The
``require(*codes)`` dependency consumes it; downstream code can also
read it via the dependency graph when it needs ownership filtering
or audit attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UUID
    tenant_id: UUID | None = None
    role: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)


__all__ = ["Actor"]
