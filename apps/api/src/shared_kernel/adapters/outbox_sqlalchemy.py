"""SQLAlchemy adapter for OutboxWriter.

Inserts into `outbox` using the session of the active UnitOfWork so the row is
committed atomically with the aggregate change.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_INSERT_SQL = text(
    """
    INSERT INTO outbox (
        event_id, tenant_id, event_type, event_version,
        aggregate_type, aggregate_id, payload, correlation_id
    ) VALUES (
        :event_id, :tenant_id, :event_type, :event_version,
        :aggregate_type, :aggregate_id, CAST(:payload AS jsonb), :correlation_id
    )
    """
)


class OutboxWriterSqlAlchemy:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

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
    ) -> None:
        import json

        await self._uow.current_session.execute(
            _INSERT_SQL,
            {
                "event_id": event_id,
                "tenant_id": tenant_id,
                "event_type": event_type,
                "event_version": event_version,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "payload": json.dumps(payload),
                "correlation_id": correlation_id,
            },
        )
