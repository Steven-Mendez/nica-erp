"""Shared fixtures for identity application-layer unit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest

from shared_kernel.adapters.context import CurrentUser


class FakeUow:
    """Minimal :class:`UnitOfWork` stand-in for use-case tests.

    Tracks ``begin`` count and whether the most recent block committed or
    rolled back, so tests can assert transactional intent without a real DB.
    """

    def __init__(self) -> None:
        self.begin_count = 0
        self.committed = False
        self.rolled_back = False

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[Any]:
        self.begin_count += 1
        try:
            yield None
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@pytest.fixture
def fake_uow() -> Iterator[FakeUow]:
    yield FakeUow()


@pytest.fixture
def current_user() -> CurrentUser:
    return CurrentUser(
        user_id=uuid4(),
        email="a@b.io",
        external_sub="sub-1",
        active_tenant=None,
    )
