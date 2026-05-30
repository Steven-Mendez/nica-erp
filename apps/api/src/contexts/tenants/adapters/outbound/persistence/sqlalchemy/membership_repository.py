"""SQLAlchemy adapter for :class:`MembershipRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text

from contexts.tenants.domain import Membership, Role
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_COLUMNS = "id, user_id, tenant_id, role, status, joined_at, removed_at"

# The SQL strings below interpolate only the trusted module-level
# `_COLUMNS` constant — no user input reaches the SQL. Filter values are
# bound via `:param` placeholders.
_SELECT_FIND_SQL = (
    f"SELECT {_COLUMNS} FROM tenant_members WHERE user_id = :user_id AND tenant_id = :tenant_id"
)
_SELECT_BY_TENANT_SQL = (
    f"SELECT {_COLUMNS} FROM tenant_members WHERE tenant_id = :tenant_id ORDER BY joined_at ASC"
)
_SELECT_ACTIVE_FOR_USER_SQL = (
    f"SELECT {_COLUMNS} FROM tenant_members "
    "WHERE user_id = :user_id AND status = 'active' "
    "ORDER BY joined_at ASC"
)
_SELECT_FIND = text(
    _SELECT_FIND_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_BY_TENANT = text(
    _SELECT_BY_TENANT_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_ACTIVE_FOR_USER = text(
    _SELECT_ACTIVE_FOR_USER_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text

_INSERT = text(
    "INSERT INTO tenant_members ("
    "id, user_id, tenant_id, role, status, joined_at, removed_at"
    ") VALUES ("
    ":id, :user_id, :tenant_id, :role, :status, :joined_at, :removed_at"
    ")"
)

_UPDATE = text(
    "UPDATE tenant_members SET "
    "role = :role, status = :status, removed_at = :removed_at "
    "WHERE id = :id"
)


class MembershipRepositorySqlAlchemy:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def add(self, membership: Membership) -> None:
        await self._uow.current_session.execute(_INSERT, self._params(membership))

    async def update(self, membership: Membership) -> None:
        await self._uow.current_session.execute(
            _UPDATE,
            {
                "id": membership.id,
                "role": membership.role.value,
                "status": membership.status,
                "removed_at": membership.removed_at,
            },
        )

    async def find(self, *, user_id: UUID, tenant_id: UUID) -> Membership | None:
        result = await self._uow.current_session.execute(
            _SELECT_FIND, {"user_id": user_id, "tenant_id": tenant_id}
        )
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[Membership]:
        result = await self._uow.current_session.execute(
            _SELECT_BY_TENANT, {"tenant_id": tenant_id}
        )
        return [self._hydrate(row) for row in result.mappings().all()]

    async def list_active_for_user(self, user_id: UUID) -> list[Membership]:
        result = await self._uow.current_session.execute(
            _SELECT_ACTIVE_FOR_USER, {"user_id": user_id}
        )
        return [self._hydrate(row) for row in result.mappings().all()]

    @staticmethod
    def _hydrate(row: RowMapping) -> Membership:
        return Membership.hydrate(
            id_=row["id"],
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            role=Role(row["role"]),
            status=row["status"],
            joined_at=_as_dt(row["joined_at"]),
            removed_at=row["removed_at"]
            if row["removed_at"] is None
            else _as_dt(row["removed_at"]),
        )

    @staticmethod
    def _params(membership: Membership) -> dict[str, Any]:
        return {
            "id": membership.id,
            "user_id": membership.user_id,
            "tenant_id": membership.tenant_id,
            "role": membership.role.value,
            "status": membership.status,
            "joined_at": membership.joined_at,
            "removed_at": membership.removed_at,
        }


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError(f"Expected datetime, got {type(value).__name__}")


__all__ = ["MembershipRepositorySqlAlchemy"]
