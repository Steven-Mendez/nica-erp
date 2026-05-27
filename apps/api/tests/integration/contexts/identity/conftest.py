"""Fixtures shared by identity-context integration tests.

The Postgres testcontainer and ``session_factory`` come from the
top-level :mod:`apps.api.conftest`. We add an :func:`isolated_uow`
fixture that wipes ``users`` and ``auth_local_users`` between tests so
the suite is order-independent, plus a :class:`RecordingEmailSender`
fake that captures every send for assertion.

These tests require ``auth_local_users`` to exist, which in turn requires
``APP_ENV=local`` at the time the migrations run. The integration suite
SHOULD be invoked with::

    APP_ENV=local LOCAL_JWT_SECRET=test-secret-very-long-32-chars-yes \\
        uv run pytest tests/integration/contexts/identity -m integration

Tests will be skipped when the table is absent (e.g. if the suite was
invoked without ``APP_ENV=local``).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.identity.application.ports.outbound import EmailSender
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


@dataclass
class SentEmail:
    to: str
    subject: str
    html: str
    text: str


@dataclass
class RecordingEmailSender(EmailSender):
    """Test double that records every :meth:`send` call."""

    sent: list[SentEmail] = field(default_factory=list)
    fail_with: Exception | None = None

    async def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(SentEmail(to=to, subject=subject, html=html, text=text))


@pytest.fixture
def email_sender() -> RecordingEmailSender:
    return RecordingEmailSender()


@pytest_asyncio.fixture
async def isolated_uow(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """Yield a fresh UoW with the identity tables truncated.

    Skips the test when ``auth_local_users`` does not exist — that means
    the test session was started without ``APP_ENV=local`` and migration
    0002 did not create the local-only table.
    """

    async with session_factory() as probe:
        exists = (
            await probe.execute(text("SELECT to_regclass('public.auth_local_users') IS NOT NULL"))
        ).scalar_one()
    if not exists:
        pytest.skip(
            "auth_local_users missing; rerun with APP_ENV=local so "
            "migration 0002 creates the local ledger"
        )

    async with session_factory() as session:
        # users carries a FK-free row but cleaning it keeps the suite
        # idempotent across reruns.
        await session.execute(text("TRUNCATE TABLE auth_local_users RESTART IDENTITY"))
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.commit()

    yield SqlAlchemyUnitOfWork(session_factory)


@pytest.fixture
def jwt_secret() -> str:
    secret = os.environ.get("LOCAL_JWT_SECRET", "test-secret-very-long-32-chars-yes")
    return secret
