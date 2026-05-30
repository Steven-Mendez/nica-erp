"""Fixtures shared by tenants-context integration tests.

A separate ``isolated_uow`` fixture truncates the tenant tables AND
the upstream users tables so each test starts on a known state.
``app.tenant_id`` is reset to the zero-uuid sentinel before yielding
so RLS WITH CHECK clauses don't leak between tests that arrange
data under different tenant GUC values.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


@pytest_asyncio.fixture
async def isolated_uow(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """Yield a fresh UoW with all tenant + identity tables truncated."""

    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE invitations RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE tenant_members RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE tenants RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE outbox RESTART IDENTITY"))
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.commit()
    yield SqlAlchemyUnitOfWork(session_factory)


@pytest_asyncio.fixture
async def seeded_user_id(
    session_factory: async_sessionmaker[AsyncSession],
    isolated_uow: SqlAlchemyUnitOfWork,
) -> UUID:
    """Insert a ``users`` row and return its id.

    Used by tests that need a valid FK target for ``tenant_members``
    without exercising the identity context.
    """

    user_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            text("INSERT INTO users (id, external_sub, email) VALUES (:id, :sub, :email)"),
            {"id": user_id, "sub": str(user_id), "email": f"{user_id}@test.dev"},
        )
        await session.commit()
    return user_id
