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
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

# Hypothesis profiles. ``dev`` is the local default (snappy);
# ``ci`` removes the deadline (cold CI agents can be > 200 ms slow
# on first call) and raises the example budget. Select via
# ``HYPOTHESIS_PROFILE=ci`` in the workflow.
hypothesis_settings.register_profile("dev", deadline=None)
hypothesis_settings.register_profile(
    "ci",
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

# Default APP_ENV / LOCAL_JWT_SECRET so `bootstrap.settings.Settings` (which
# rejects an unset APP_ENV per the api-bootstrap spec) imports cleanly during
# test collection. `os.environ.setdefault` runs before any module-level
# `Settings()` call further down the import graph, which `monkeypatch` can't
# guarantee since fixtures run after collection.
os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("LOCAL_JWT_SECRET", "test-secret-very-long-32-chars-yes-please-1234")

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
    """Async DB URL the **app** uses — connects as the ``nica_erp_app`` role.

    The role is created in ``_run_migrations`` and is NOBYPASSRLS so the
    e2e tenant-isolation gate exercises the same RLS posture production
    must rely on. Alembic itself still runs as the superuser
    (see :func:`_run_migrations`) because some migrations create
    extensions and policies that require ownership.
    """

    sync_url: str = postgres_container.get_connection_url()
    # Replace the superuser credentials with the app role's. The
    # ``nica_erp_app`` role is provisioned by ``_run_migrations`` before
    # this URL is consumed for the first time.
    asyncpg_url = sync_url.replace("+psycopg2", "+asyncpg")
    # ``postgresql+asyncpg://test:test@host:port/test`` → swap user:pw.
    head, sep, tail = asyncpg_url.partition("://")
    _userinfo, _sep, hostpart = tail.partition("@")
    return f"{head}{sep}nica_erp_app:app@{hostpart}"


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
    # PostgreSQL superusers bypass RLS unconditionally — even with
    # ``FORCE ROW LEVEL SECURITY``. Production must therefore connect as
    # a NOBYPASSRLS role; the testcontainer defaults to a superuser, so
    # the tenant-isolation e2e gate would silently pass when RLS is
    # broken. We provision a dedicated ``nica_erp_app`` role here and
    # require the e2e fixture to ``SET ROLE`` it on every checkout (see
    # ``tests/e2e/conftest.py``).
    import psycopg  # imported lazily; psycopg is already a dev dep via alembic

    # ``psycopg.connect`` expects a libpq DSN, not the SQLAlchemy-style
    # URL the testcontainer hands out. Strip the SQLAlchemy dialect prefix.
    sa_url = postgres_container.get_connection_url().replace("+psycopg2", "")
    libpq_url = sa_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(libpq_url, autocommit=True) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "DO $$ BEGIN "
                "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nica_erp_app') THEN "
                "    CREATE ROLE nica_erp_app LOGIN NOBYPASSRLS PASSWORD 'app'; "
                "  END IF; "
                "END $$;"
            )
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO nica_erp_app")
            # ``GRANT ALL`` covers SELECT/INSERT/UPDATE/DELETE/TRUNCATE/
            # REFERENCES/TRIGGER — TRUNCATE is required by the per-test
            # cleanup in ``tests/e2e/conftest.py``.
            cur.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nica_erp_app")
            cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nica_erp_app")
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON TABLES TO nica_erp_app"
            )


@pytest_asyncio.fixture
async def session_factory(database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield an ``async_sessionmaker`` whose sessions act as ``nica_erp_app``.

    The URL itself authenticates as ``nica_erp_app`` (provisioned by
    ``_run_migrations``), so the NOBYPASSRLS attribute applies for
    every query. Tests that need superuser semantics (e.g. seeding the
    database past RLS) must open their own engine off the master
    connection URL.
    """

    engine = create_async_engine(database_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
