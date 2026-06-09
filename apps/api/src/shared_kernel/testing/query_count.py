"""Query-budget assertion for N+1 regression gates."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _resolve_sync_engine(target: Any) -> Engine:
    """Find the sync ``Engine`` behind any of the common test handles."""

    if isinstance(target, Engine):
        return target
    if isinstance(target, AsyncEngine):
        return target.sync_engine
    if isinstance(target, AsyncSession):
        bind = target.sync_session.get_bind()
        return bind if isinstance(bind, Engine) else bind.engine
    if isinstance(target, async_sessionmaker):
        factory_bind = target.kw.get("bind")
        if isinstance(factory_bind, AsyncEngine):
            return factory_bind.sync_engine
        if isinstance(factory_bind, Engine):
            return factory_bind
    raise TypeError(
        "assert_query_count expects an Engine, AsyncEngine, AsyncSession or a "
        f"bound async_sessionmaker; got {type(target).__name__}"
    )


@asynccontextmanager
async def assert_query_count(target: Any, *, max_queries: int) -> AsyncIterator[list[str]]:
    """Fail if the block issues more than ``max_queries`` SQL statements.

    Counts every statement that reaches the database through ``target``'s
    engine — including ``set_config`` calls emitted by the unit of work —
    so budgets must account for session setup, not just the queries the
    use case owns. Yields the recorded statements so a failing test can
    print exactly what ran.
    """

    engine = _resolve_sync_engine(target)
    statements: list[str] = []

    def _record(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    if len(statements) > max_queries:
        listing = "\n  ".join(statements)
        raise AssertionError(
            f"query budget exceeded: {len(statements)} statements > {max_queries} allowed\n"
            f"  {listing}"
        )


__all__ = ["assert_query_count"]
