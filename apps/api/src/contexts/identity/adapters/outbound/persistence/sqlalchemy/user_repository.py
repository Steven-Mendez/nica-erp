"""SQLAlchemy adapter for the :class:`UserRepository` port.

Builds Core statements over the shared ``users`` table metadata against
the active :class:`SqlAlchemyUnitOfWork`'s session — no ORM mapping.
The ``User`` aggregate stays free of SQLAlchemy, mirroring the
``OutboxWriterSqlAlchemy`` pattern in :mod:`shared_kernel.adapters`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, bindparam, insert, select, update

from contexts.identity.domain import Email, User
from shared_kernel.adapters.tables import users
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_SELECT_BY_ID = select(users).where(users.c.id == bindparam("id"))
_SELECT_BY_EXTERNAL_SUB = select(users).where(users.c.external_sub == bindparam("external_sub"))
_INSERT = insert(users).values(
    id=bindparam("id"),
    external_sub=bindparam("external_sub"),
    email=bindparam("email"),
    display_name=bindparam("display_name"),
    locale=bindparam("locale"),
    timezone=bindparam("timezone"),
    preferences=bindparam("preferences"),
    created_at=bindparam("created_at"),
    updated_at=bindparam("updated_at"),
)
# ``bindparam("id")`` is reserved inside update() because it names a
# column of the target table; the WHERE param needs the ``b_`` prefix.
_UPDATE = (
    update(users)
    .where(users.c.id == bindparam("b_id"))
    .values(
        display_name=bindparam("display_name"),
        locale=bindparam("locale"),
        timezone=bindparam("timezone"),
        preferences=bindparam("preferences"),
        updated_at=bindparam("updated_at"),
    )
)


class UserRepositorySqlAlchemy:
    """``UserRepository`` adapter backed by the ``users`` table."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._uow.current_session.execute(_SELECT_BY_ID, {"id": user_id})
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def list_by_ids(self, user_ids: Iterable[UUID]) -> Sequence[User]:
        ids = list({uid for uid in user_ids})
        if not ids:
            return []
        result = await self._uow.current_session.execute(select(users).where(users.c.id.in_(ids)))
        return [self._hydrate(row) for row in result.mappings().all()]

    async def get_by_external_sub(self, external_sub: str) -> User | None:
        result = await self._uow.current_session.execute(
            _SELECT_BY_EXTERNAL_SUB, {"external_sub": external_sub}
        )
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def add(self, user: User) -> None:
        await self._uow.current_session.execute(_INSERT, self._params(user))

    async def update(self, user: User) -> None:
        await self._uow.current_session.execute(
            _UPDATE,
            {
                "b_id": user.id,
                "display_name": user.display_name,
                "locale": user.locale,
                "timezone": user.timezone,
                "preferences": user.preferences,
                "updated_at": user.updated_at,
            },
        )

    # Internal helpers ---------------------------------------------------------
    @staticmethod
    def _hydrate(row: RowMapping) -> User:
        preferences = row["preferences"]
        return User(
            id_=row["id"],
            external_sub=row["external_sub"],
            email=Email.parse(row["email"]),
            display_name=row["display_name"],
            locale=row["locale"],
            timezone=row["timezone"],
            preferences=dict(preferences) if preferences else {},
            created_at=_as_datetime(row["created_at"]),
            updated_at=_as_datetime(row["updated_at"]),
        )

    @staticmethod
    def _params(user: User) -> dict[str, object]:
        return {
            "id": user.id,
            "external_sub": user.external_sub,
            "email": user.email.value,
            "display_name": user.display_name,
            "locale": user.locale,
            "timezone": user.timezone,
            "preferences": user.preferences,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }


def _as_datetime(value: Any) -> datetime:
    """Narrow a row value to :class:`datetime` for mypy-strict happiness."""

    if isinstance(value, datetime):
        return value
    raise TypeError(f"Expected datetime, got {type(value).__name__}")


__all__ = ["UserRepositorySqlAlchemy"]
