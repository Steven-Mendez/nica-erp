from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class UnitOfWork(Protocol):
    """Transactional boundary.

    `begin()` is an async context manager that yields an `AsyncSession`.
    On exit without error, the transaction commits; on exception, it rolls back.
    """

    def begin(self) -> AbstractAsyncContextManager[AsyncSession]: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
