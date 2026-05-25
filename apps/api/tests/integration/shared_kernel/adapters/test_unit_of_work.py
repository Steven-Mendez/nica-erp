# apps/api/tests/integration/shared_kernel/adapters/test_unit_of_work.py
"""Integration test for SqlAlchemyUnitOfWork against a real Postgres testcontainer.

Exercises the commit-on-success / rollback-on-exception contract and the
session-unavailable invariant outside `begin()`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.integration
async def test_uow_begin_commits_on_normal_exit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    uow = SqlAlchemyUnitOfWork(session_factory)
    async with uow.begin() as session:
        row = (await session.execute(text("SELECT 1"))).scalar_one()
    assert row == 1


@pytest.mark.integration
async def test_uow_begin_rolls_back_on_exception(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    uow = SqlAlchemyUnitOfWork(session_factory)

    class BoomError(RuntimeError):
        pass

    with pytest.raises(BoomError):
        async with uow.begin() as session:
            await session.execute(text("CREATE TEMP TABLE _uow_probe (x INT) ON COMMIT DROP"))
            raise BoomError("rollback path")

    async with uow.begin() as session:
        exists = (
            await session.execute(text("SELECT to_regclass('pg_temp._uow_probe') IS NOT NULL"))
        ).scalar_one()
    assert exists is False


@pytest.mark.integration
async def test_uow_session_unavailable_outside_begin(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    uow = SqlAlchemyUnitOfWork(session_factory)
    with pytest.raises(RuntimeError):
        _ = uow.current_session
