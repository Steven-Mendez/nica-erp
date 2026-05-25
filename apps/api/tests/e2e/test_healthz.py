# apps/api/tests/e2e/test_healthz.py
"""E2E: GET /healthz → db ok + Alembic revision.

Mounts the real FastAPI app, overrides the UoW dependency to point at the
session_factory bound to the shared testcontainer, and asserts the payload
contract the frontend reads.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bootstrap import api as api_module
from bootstrap import db as db_module
from bootstrap.db import get_uow
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.e2e
async def test_healthz_reports_db_ok_and_alembic_revision(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_module, "get_session_factory", lambda: session_factory)

    async def _override_get_uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
        yield SqlAlchemyUnitOfWork(session_factory)

    api_module.app.dependency_overrides[get_uow] = _override_get_uow
    try:
        transport = ASGITransport(app=api_module.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
    finally:
        api_module.app.dependency_overrides.pop(get_uow, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["alembic_revision"] == "0001_shared_kernel"
