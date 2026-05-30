"""Sprint-gate test — DB ``role_permissions`` must match the Python catalog."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.permissions.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    TENANT_PERMISSIONS,
)


@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as sess:
        yield sess


@pytest.mark.asyncio
async def test_role_permission_matrix(session: AsyncSession) -> None:
    """``role_permissions`` rows must match ``DEFAULT_ROLE_PERMISSIONS``."""

    result = await session.execute(
        text("SELECT role, permission FROM role_permissions ORDER BY role, permission")
    )
    rows: set[tuple[str, str]] = {(r[0], r[1]) for r in result.all()}

    expected: set[tuple[str, str]] = set()
    for role, codes in DEFAULT_ROLE_PERMISSIONS.items():
        for code in codes:
            expected.add((role, code))

    missing = expected - rows
    extra = rows - expected
    assert not missing, f"role_permissions missing rows: {missing}"
    assert not extra, f"role_permissions has unexpected rows: {extra}"


@pytest.mark.asyncio
async def test_permissions_table_matches_catalog(session: AsyncSession) -> None:
    result = await session.execute(text("SELECT code FROM permissions ORDER BY code"))
    db_codes = {r[0] for r in result.all()}
    catalog_codes = {p.code for p in TENANT_PERMISSIONS}
    missing = catalog_codes - db_codes
    assert not missing, f"permissions table missing codes: {missing}"
