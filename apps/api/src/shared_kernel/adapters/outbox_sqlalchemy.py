"""SQLAlchemy adapter for OutboxWriter.

Inserts into `outbox` using the session of the active UnitOfWork so the row is
committed atomically with the aggregate change.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import insert

from shared_kernel.adapters.tables import outbox
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


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
        await self._uow.current_session.execute(
            insert(outbox).values(
                event_id=event_id,
                tenant_id=tenant_id,
                event_type=event_type,
                event_version=event_version,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                correlation_id=correlation_id,
            )
        )
