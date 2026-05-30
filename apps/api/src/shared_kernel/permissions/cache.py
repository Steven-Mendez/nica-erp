"""Process-local TTL cache for ``role -> frozenset[permission_code]``.

The default TTL is 60 s. Concurrent cache misses for the same role
serialise on an ``asyncio.Lock`` so a burst of requests does not
stampede the database. A reseed of ``role_permissions`` propagates
within at most one TTL window without explicit invalidation.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(slots=True)
class PermissionCache:
    """In-memory ``role → (expires_at, permissions)`` cache."""

    ttl_seconds: float = 60.0
    _store: dict[str, tuple[float, frozenset[str]]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(
        self,
        role: str,
        loader: Callable[[str], Awaitable[frozenset[str]]],
    ) -> frozenset[str]:
        now = time.monotonic()
        hit = self._store.get(role)
        if hit is not None and now - hit[0] < self.ttl_seconds:
            return hit[1]
        async with self._lock:
            # Re-check after acquiring the lock — a sibling coroutine may have
            # populated the entry while we waited.
            hit = self._store.get(role)
            if hit is not None and time.monotonic() - hit[0] < self.ttl_seconds:
                return hit[1]
            permissions = await loader(role)
            self._store[role] = (time.monotonic(), permissions)
            return permissions

    def clear(self) -> None:
        self._store.clear()


__all__ = ["PermissionCache"]
