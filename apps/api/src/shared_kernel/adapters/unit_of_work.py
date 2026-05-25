"""SQLAlchemy-backed UnitOfWork.

`begin()` opens an `AsyncSession` and a transaction; on normal exit it commits,
on exception it rolls back. The active session is exposed via `current_session`
so adapters scoped to the request (e.g. `OutboxWriterSqlAlchemy`) can join the
same transaction without going through DI a second time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def current_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active; use `async with uow.begin():`.")
        return self._session

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        self._session = session
        try:
            async with session.begin():
                yield session
        finally:
            await session.close()
            self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("commit() without an active session.")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("rollback() without an active session.")
        await self._session.rollback()
