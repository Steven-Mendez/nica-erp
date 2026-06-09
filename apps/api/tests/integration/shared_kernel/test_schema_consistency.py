"""Schema-vs-metadata consistency guard.

Persistence adapters build their statements from the Core ``Table``
metadata on the shared registry. If a migration drops, renames, or
retypes a column without a matching metadata update (or vice versa),
statements fail at runtime — typically inside a deploy, not a test.
This guard fails the integration suite on any column-level drift
between the metadata and the Alembic-migrated database.

Only modeled tables are compared, and only at column granularity:
constraints, indexes, server defaults, and RLS policies are
intentionally not modeled — the hand-written migrations own those.
``--autogenerate`` stays off in ``alembic/env.py``; this test is the
sole consumer of the autogenerate comparison machinery.
"""

from __future__ import annotations

from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.identity.adapters.outbound.persistence.sqlalchemy.tables import (
    auth_local_refresh_tokens,
    auth_local_users,
)
from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tables import (
    invitations,
    tenant_members,
)
from shared_kernel.adapters.tables import metadata, outbox, role_permissions, tenants, users

pytestmark = pytest.mark.integration

_MODELED_TABLE_NAMES = frozenset(
    table.name
    for table in (
        users,
        tenants,
        outbox,
        role_permissions,
        auth_local_users,
        auth_local_refresh_tokens,
        tenant_members,
        invitations,
    )
)


def _column_level_diffs(sync_conn: Connection) -> list[Any]:
    def include_object(
        obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
    ) -> bool:
        if type_ == "table":
            return name in _MODELED_TABLE_NAMES
        # The metadata models columns only; everything below column
        # granularity is owned by the migrations and must not count
        # as drift.
        if type_ in {"index", "unique_constraint", "foreign_key_constraint", "check_constraint"}:
            return False
        return True

    ctx = MigrationContext.configure(
        sync_conn,
        opts={"compare_type": True, "include_object": include_object},
    )
    return compare_metadata(ctx, metadata)


def _render(diff: Any) -> str:
    # ``modify_*`` entries arrive as single-element lists of tuples;
    # flatten so the failure message reads one drift per line.
    if isinstance(diff, list):
        return "; ".join(str(entry) for entry in diff)
    return str(diff)


async def test_metadata_matches_migrated_schema(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        conn = await session.connection()
        diffs = await conn.run_sync(_column_level_diffs)

    rendered = "\n".join(f"  - {_render(d)}" for d in diffs)
    assert diffs == [], (
        "Core Table metadata drifted from the Alembic-migrated schema "
        "(missing/extra columns, type or nullability mismatch, or a "
        f"modeled table absent from the database):\n{rendered}\n"
        "Update the matching tables.py module in the same PR as the "
        "migration."
    )
