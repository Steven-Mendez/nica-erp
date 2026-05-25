# apps/api/conftest.py
"""Root pytest config.

Tests live under `apps/api/tests/` and are auto-marked by their top-level
folder so contributors never add the marker by hand and `pytest -m unit` /
`-m integration` filter correctly:

- `tests/unit/`        → `unit`
- `tests/integration/` → `integration`
- `tests/contract/`    → `contract`
- `tests/e2e/`         → `e2e`

The Postgres testcontainer + async session_factory live here so integration
and e2e suites share the same database fixture and one container is reused
for the whole session.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

_API_ROOT = Path(__file__).resolve().parent  # apps/api/

_MARKER_BY_FOLDER = {
    "unit": pytest.mark.unit,
    "integration": pytest.mark.integration,
    "contract": pytest.mark.contract,
    "e2e": pytest.mark.e2e,
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(item.path)
        try:
            rel = path.relative_to(_API_ROOT)
        except ValueError:
            continue
        parts = rel.parts
        if parts[:1] != ("tests",) or len(parts) < 2:
            continue
        marker = _MARKER_BY_FOLDER.get(parts[1])
        if marker is not None:
            item.add_marker(marker)


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    sync_url: str = postgres_container.get_connection_url()
    return sync_url.replace("+psycopg2", "+asyncpg")


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(postgres_container: PostgresContainer) -> None:
    alembic_url = postgres_container.get_connection_url().replace("+psycopg2", "+psycopg")
    env = {**os.environ, "ALEMBIC_DATABASE_URL": alembic_url}
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=_API_ROOT,
        env=env,
        check=True,
    )


@pytest_asyncio.fixture
async def session_factory(database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
