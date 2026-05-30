"""Schema-vs-repository consistency guard.

Repositories under ``contexts/*/adapters/outbound/persistence/sqlalchemy/``
build their SQL by interpolating a module-level ``_COLUMNS`` constant.
If a migration drops one of those columns (or renames it), the SQL fails
at runtime — typically inside a deploy, not a test. This guard fails
the integration suite the moment the SQL the repository wants to emit
references a column that does not exist in the migrated database.

Tables checked: ``tenants``, ``tenant_members``, ``invitations``,
``auth_local_users``, ``users``. ``users`` does not expose a
``_COLUMNS`` constant; the expected list is asserted explicitly to
match the columns the inline SQL in ``user_repository`` references.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.identity.adapters.outbound.persistence.sqlalchemy import auth_local_users
from contexts.tenants.adapters.outbound.persistence.sqlalchemy import (
    invitation_repository,
    membership_repository,
    tenant_repository,
)

pytestmark = pytest.mark.integration


def _split_columns(raw: str) -> list[str]:
    """Split a ``_COLUMNS`` constant string into individual names."""

    return [name.strip() for name in raw.split(",") if name.strip()]


_REPOSITORY_TABLES: list[tuple[str, list[str]]] = [
    ("tenants", _split_columns(tenant_repository._COLUMNS)),
    ("tenant_members", _split_columns(membership_repository._COLUMNS)),
    ("invitations", _split_columns(invitation_repository._COLUMNS)),
    ("auth_local_users", _split_columns(auth_local_users._COLUMNS)),
    # ``user_repository`` builds inline SQL — these columns are the ones
    # referenced in its SELECT, INSERT and UPDATE strings today. If the
    # set drifts, this list must be updated in the same PR as the SQL.
    (
        "users",
        [
            "id",
            "external_sub",
            "email",
            "preferences",
            "created_at",
            "updated_at",
        ],
    ),
]


async def _columns_in(session: AsyncSession, table: str) -> set[str]:
    rows = await session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table"
        ),
        {"table": table},
    )
    return {row[0] for row in rows.all()}


@pytest.mark.parametrize("table,expected", _REPOSITORY_TABLES, ids=lambda x: str(x))
async def test_repository_columns_exist_in_database(
    session_factory: async_sessionmaker[AsyncSession],
    table: str,
    expected: list[str],
) -> None:
    async with session_factory() as session:
        actual = await _columns_in(session, table)

    missing = sorted(set(expected) - actual)
    assert missing == [], (
        f"Table {table!r} is missing columns referenced by the repository SQL: "
        f"{missing}. Either the migration is incomplete or the repository "
        f"SQL drifted past the schema."
    )


async def test_every_checked_table_actually_exists(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sanity: every table this guard checks must exist after migrations."""

    async with session_factory() as session:
        rows = await session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        existing = {row[0] for row in rows.all()}

    expected_tables = {name for name, _ in _REPOSITORY_TABLES}
    missing = sorted(expected_tables - existing)
    assert missing == [], (
        f"Tables referenced by repositories are absent from the database: "
        f"{missing}. A migration was likely dropped without retiring the "
        f"corresponding repository."
    )
