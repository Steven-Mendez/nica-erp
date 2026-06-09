"""SQLAlchemy adapter for :class:`MembershipRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, bindparam, text
from sqlalchemy.sql.elements import BindParameter

from contexts.tenants.application.use_cases.get_my_tenants import MyTenantView
from contexts.tenants.application.use_cases.list_members import (
    ListMembersQuery,
    MemberView,
)
from contexts.tenants.domain import Membership, Role
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

# Whitelist for `ORDER BY` — user input never reaches the SQL string;
# only these mappings do.
_SORT_COLUMNS: dict[str, str] = {
    "joined_at": "tm.joined_at",
    "display_name": "u.display_name",
    "email": "u.email",
    "role": "tm.role",
}
_SORT_DIRECTIONS: dict[str, str] = {"asc": "ASC", "desc": "DESC"}

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
# INNER JOIN drops memberships whose tenant row is missing — `tenants`
# has no RLS, so an absent row means orphaned data, not a visibility
# boundary; the picker should skip it rather than crash.
_SELECT_ACTIVE_WITH_TENANT_SQL = (
    "SELECT tm.tenant_id, t.name, tm.role, t.status, tm.joined_at "
    "FROM tenant_members tm JOIN tenants t ON t.id = tm.tenant_id "
    "WHERE tm.user_id = :user_id AND tm.status = 'active' "
    "ORDER BY tm.joined_at ASC"
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
_SELECT_ACTIVE_WITH_TENANT = text(
    _SELECT_ACTIVE_WITH_TENANT_SQL
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
        # Only validated whitelist tokens (`where_sql`, `sort_col`,
        # `sort_dir`) are interpolated into the SQL string. All
        # user-typed values (`q`, roles/statuses, limit, offset, tenant
        # id) reach the database exclusively via bound parameters built
        # in `_build_filter` and `_expanding_binds`.
        where_sql, params = _build_filter(query)
        sort_col = _SORT_COLUMNS[query.sort]
        sort_dir = _SORT_DIRECTIONS[query.dir]
        # `user_id` tiebreaker keeps pagination deterministic when the
        # primary sort column has ties (e.g. two members sharing a
        # `joined_at` from a bulk import).
        page_sql_str = (
            "SELECT tm.id, tm.user_id, tm.tenant_id, tm.role, tm.status, "
            "tm.joined_at, tm.removed_at, u.display_name, u.email "
            "FROM tenant_members tm LEFT JOIN users u ON u.id = tm.user_id "
            f"{where_sql} "
            f"ORDER BY {sort_col} {sort_dir}, tm.user_id ASC "
            "LIMIT :limit OFFSET :offset"
        )
        count_sql_str = (
            "SELECT COUNT(*) AS total "
            "FROM tenant_members tm LEFT JOIN users u ON u.id = tm.user_id "
            f"{where_sql}"
        )
        page_sql = text(page_sql_str).bindparams(
            *_expanding_binds(query)
        )  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        count_sql = text(count_sql_str).bindparams(
            *_expanding_binds(query)
        )  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text

        page_params = {**params, "limit": query.limit, "offset": query.offset}
        page_result = await self._uow.current_session.execute(page_sql, page_params)
        items = [_hydrate_view(row) for row in page_result.mappings().all()]

        count_result = await self._uow.current_session.execute(count_sql, params)
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


def _build_filter(query: ListMembersQuery) -> tuple[str, dict[str, Any]]:
    """Build the WHERE clause + bound parameters for ``list_page``.

    Every dynamic value lands in ``params`` and is bound by name; the
    returned string contains only the placeholder names and the
    column references — no user input.
    """

    clauses: list[str] = ["tm.tenant_id = :tenant_id"]
    params: dict[str, Any] = {"tenant_id": query.tenant_id}

    if query.q is not None and len(query.q) > 0:
        # Escape LIKE metacharacters so a search for "100%" doesn't
        # collapse into a match-all. We pick `\` as the escape char
        # and tell Postgres about it via the `ESCAPE` clause.
        needle = query.q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["needle"] = f"%{needle}%"
        clauses.append(
            "("
            "LOWER(u.display_name) LIKE :needle ESCAPE '\\' "
            "OR LOWER(u.email) LIKE :needle ESCAPE '\\' "
            "OR LOWER(tm.user_id::text) LIKE :needle ESCAPE '\\'"
            ")"
        )

    if len(query.roles) > 0:
        clauses.append("tm.role IN :roles")
        params["roles"] = [r.value for r in query.roles]

    if len(query.statuses) > 0:
        clauses.append("tm.status IN :statuses")
        params["statuses"] = list(query.statuses)

    return "WHERE " + " AND ".join(clauses), params


def _expanding_binds(query: ListMembersQuery) -> tuple[BindParameter[Any], ...]:
    """Declare the IN-list BindParameters that are present in this call.

    SQLAlchemy needs ``expanding=True`` to turn a list into a tuple of
    placeholders. We declare them conditionally so a query without
    role / status filters doesn't ship empty arrays.
    """

    binds: list[BindParameter[Any]] = []
    if len(query.roles) > 0:
        binds.append(bindparam("roles", expanding=True))
    if len(query.statuses) > 0:
        binds.append(bindparam("statuses", expanding=True))
    return tuple(binds)


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
