"""SQLAlchemy adapter for the :class:`UserRepository` port.

Uses raw SQL via :func:`sqlalchemy.text` against the active
:class:`SqlAlchemyUnitOfWork`'s session — no ORM mapping. The ``User``
aggregate stays free of SQLAlchemy, mirroring the
``OutboxWriterSqlAlchemy`` pattern in :mod:`shared_kernel.adapters`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, bindparam, text

from contexts.identity.domain import Email, User
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_SELECT_BY_ID = text(
    "SELECT id, external_sub, email, display_name, locale, timezone, "
    "preferences, created_at, updated_at FROM users WHERE id = :id"
)
_SELECT_BY_IDS = text(
    "SELECT id, external_sub, email, display_name, locale, timezone, "
    "preferences, created_at, updated_at FROM users WHERE id IN :ids"
).bindparams(bindparam("ids", expanding=True))
_SELECT_BY_EXTERNAL_SUB = text(
    "SELECT id, external_sub, email, display_name, locale, timezone, "
    "preferences, created_at, updated_at FROM users WHERE external_sub = :external_sub"
)
_INSERT = text(
    "INSERT INTO users ("
    "id, external_sub, email, display_name, locale, timezone, preferences, "
    "created_at, updated_at"
    ") VALUES ("
    ":id, :external_sub, :email, :display_name, :locale, :timezone, "
    "CAST(:preferences AS jsonb), :created_at, :updated_at"
    ")"
)
_UPDATE = text(
    "UPDATE users SET "
    "display_name = :display_name, "
    "locale = :locale, "
    "timezone = :timezone, "
    "preferences = CAST(:preferences AS jsonb), "
    "updated_at = :updated_at "
    "WHERE id = :id"
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
        result = await self._uow.current_session.execute(_SELECT_BY_IDS, {"ids": ids})
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
                "id": user.id,
                "display_name": user.display_name,
                "locale": user.locale,
                "timezone": user.timezone,
                "preferences": json.dumps(user.preferences),
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
            "preferences": json.dumps(user.preferences),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }


def _as_datetime(value: Any) -> datetime:
    """Narrow a row value to :class:`datetime` for mypy-strict happiness."""

    if isinstance(value, datetime):
        return value
    raise TypeError(f"Expected datetime, got {type(value).__name__}")


__all__ = ["UserRepositorySqlAlchemy"]
