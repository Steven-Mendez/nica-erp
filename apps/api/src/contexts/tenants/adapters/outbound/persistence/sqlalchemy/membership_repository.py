"""SQLAlchemy adapter for :class:`MembershipRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    RowMapping,
    Text,
    asc,
    bindparam,
    cast,
    desc,
    func,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.sql.elements import ColumnElement, UnaryExpression

from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tables import tenant_members
from contexts.tenants.application.use_cases.get_my_tenants import MyTenantView
from contexts.tenants.application.use_cases.list_members import (
    ListMembersQuery,
    MemberView,
)
from contexts.tenants.domain import Membership, Role
from shared_kernel.adapters.tables import tenants, users
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_tm = tenant_members
_u = users

# Whitelist for `ORDER BY` — sort keys map to Column objects; user
# input never selects anything outside these mappings.
_SORT_COLUMNS: dict[str, ColumnElement[Any]] = {
    "joined_at": _tm.c.joined_at,
    "display_name": _u.c.display_name,
    "email": _u.c.email,
    "role": _tm.c.role,
}
_SORT_DIRECTIONS = {"asc": asc, "desc": desc}

_SELECT_FIND = select(_tm).where(
    _tm.c.user_id == bindparam("user_id"), _tm.c.tenant_id == bindparam("tenant_id")
)
_SELECT_BY_TENANT = (
    select(_tm).where(_tm.c.tenant_id == bindparam("tenant_id")).order_by(_tm.c.joined_at.asc())
)
_SELECT_ACTIVE_FOR_USER = (
    select(_tm)
    .where(_tm.c.user_id == bindparam("user_id"), _tm.c.status == "active")
    .order_by(_tm.c.joined_at.asc())
)
# INNER JOIN drops memberships whose tenant row is missing — `tenants`
# has no RLS, so an absent row means orphaned data, not a visibility
# boundary; the picker should skip it rather than crash.
_SELECT_ACTIVE_WITH_TENANT = (
    select(_tm.c.tenant_id, tenants.c.name, _tm.c.role, tenants.c.status, _tm.c.joined_at)
    .select_from(_tm.join(tenants, tenants.c.id == _tm.c.tenant_id))
    .where(_tm.c.user_id == bindparam("user_id"), _tm.c.status == "active")
    .order_by(_tm.c.joined_at.asc())
)

_INSERT = insert(_tm).values(
    id=bindparam("id"),
    user_id=bindparam("user_id"),
    tenant_id=bindparam("tenant_id"),
    role=bindparam("role"),
    status=bindparam("status"),
    joined_at=bindparam("joined_at"),
    removed_at=bindparam("removed_at"),
)

# ``bindparam("id")`` is reserved inside update() because it names a
# column of the target table; the WHERE param needs the ``b_`` prefix.
_UPDATE = (
    update(_tm)
    .where(_tm.c.id == bindparam("b_id"))
    .values(
        role=bindparam("role"),
        status=bindparam("status"),
        removed_at=bindparam("removed_at"),
    )
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
                "b_id": membership.id,
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

    async def list_active_with_tenant_for_user(self, user_id: UUID) -> list[MyTenantView]:
        result = await self._uow.current_session.execute(
            _SELECT_ACTIVE_WITH_TENANT, {"user_id": user_id}
        )
        return [
            MyTenantView(
                tenant_id=row["tenant_id"],
                name=row["name"],
                role=Role(row["role"]),
                status=row["status"],
                joined_at=_as_dt(row["joined_at"]),
            )
            for row in result.mappings().all()
        ]

    async def list_page(self, query: ListMembersQuery) -> tuple[list[MemberView], int]:
        filters = _build_filters(query)
        # `user_id` tiebreaker keeps pagination deterministic when the
        # primary sort column has ties (e.g. two members sharing a
        # `joined_at` from a bulk import).
        order: UnaryExpression[Any] = _SORT_DIRECTIONS[query.dir](_SORT_COLUMNS[query.sort])
        joined = _tm.outerjoin(_u, _u.c.id == _tm.c.user_id)

        page_stmt = (
            select(
                _tm.c.id,
                _tm.c.user_id,
                _tm.c.tenant_id,
                _tm.c.role,
                _tm.c.status,
                _tm.c.joined_at,
                _tm.c.removed_at,
                _u.c.display_name,
                _u.c.email,
            )
            .select_from(joined)
            .where(*filters)
            .order_by(order, _tm.c.user_id.asc())
            .limit(query.limit)
            .offset(query.offset)
        )
        count_stmt = select(func.count().label("total")).select_from(joined).where(*filters)

        page_result = await self._uow.current_session.execute(page_stmt)
        items = [_hydrate_view(row) for row in page_result.mappings().all()]

        count_result = await self._uow.current_session.execute(count_stmt)
        total_row = count_result.mappings().one()
        total = int(total_row["total"])
        return items, total

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


def _build_filters(query: ListMembersQuery) -> list[ColumnElement[bool]]:
    """Build the WHERE clauses for ``list_page``.

    Every user-typed value reaches the database as a bound parameter;
    the composed expressions reference columns only.
    """

    clauses: list[ColumnElement[bool]] = [_tm.c.tenant_id == query.tenant_id]

    if query.q is not None and len(query.q) > 0:
        # Escape LIKE metacharacters so a search for "100%" doesn't
        # collapse into a match-all. We pick `\` as the escape char
        # and tell Postgres about it via the `ESCAPE` clause.
        needle = query.q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{needle}%"
        clauses.append(
            or_(
                func.lower(_u.c.display_name).like(pattern, escape="\\"),
                func.lower(_u.c.email).like(pattern, escape="\\"),
                func.lower(cast(_tm.c.user_id, Text())).like(pattern, escape="\\"),
            )
        )

    if len(query.roles) > 0:
        clauses.append(_tm.c.role.in_([r.value for r in query.roles]))

    if len(query.statuses) > 0:
        clauses.append(_tm.c.status.in_(list(query.statuses)))

    return clauses


def _hydrate_view(row: RowMapping) -> MemberView:
    return MemberView(
        id=row["id"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        role=Role(row["role"]),
        status=row["status"],
        joined_at=_as_dt(row["joined_at"]),
        removed_at=None if row["removed_at"] is None else _as_dt(row["removed_at"]),
        display_name=row["display_name"],
        email=row["email"],
    )


__all__ = ["MembershipRepositorySqlAlchemy"]
