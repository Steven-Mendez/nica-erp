"""OutboxWriter port.

The concrete implementation writes the event row inside the same database
transaction as the aggregate change, so the aggregate and its emitted event
either both commit or both roll back. A separate publisher process drains
the table and forwards events to the message bus.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class OutboxWriter(Protocol):
    async def append(
        self,
        *,
        event_id: UUID,
        event_type: str,
        event_version: int,
        aggregate_type: str,
        aggregate_id: UUID,
        tenant_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
    ) -> None: ...
