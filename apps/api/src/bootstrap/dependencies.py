"""Shared HTTP dependencies (cross-context).

Each context owns its own dependency factories under
``contexts/<x>/adapters/inbound/http/dependencies.py``. This module
covers the dependencies used across multiple contexts:

- ``current_actor`` materialises the request-scoped :class:`Actor`
  from ``CurrentUserContext`` + ``TenantContext`` + the
  ``tenant_members`` / ``role_permissions`` tables, with the
  permission set cached per process (TTL from
  ``settings.permission_cache_ttl_seconds``).
- ``require(*codes)`` returns a FastAPI dependency that 403s on a
  missing code.
- ``get_request_uow`` opens the reentrant request UoW so every
  dependency in the request graph shares the same session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends
from sqlalchemy import bindparam, select

from bootstrap.container import build_request_uow
from bootstrap.settings import get_settings
from contexts.identity.application.errors import InvalidCredentialsError
from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tables import tenant_members
from shared_kernel.adapters.context import CurrentUserContext, TenantContext
from shared_kernel.adapters.tables import role_permissions
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from shared_kernel.permissions import Actor, ForbiddenError, PermissionCache

_SELECT_ROLE_PERMISSIONS = select(role_permissions.c.permission).where(
    role_permissions.c.role == bindparam("role")
)
_SELECT_ACTIVE_MEMBER_ROLE = (
    select(tenant_members.c.role)
    .where(
        tenant_members.c.user_id == bindparam("user_id"),
        tenant_members.c.tenant_id == bindparam("tenant_id"),
        tenant_members.c.status == "active",
    )
    .limit(1)
)

_settings = get_settings()
_permission_cache = PermissionCache(ttl_seconds=_settings.permission_cache_ttl_seconds)


async def get_request_uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """Yield the reentrant request UoW wrapped in ``async with uow.begin():``.

    Every dependency in the request graph that takes
    ``uow: SqlAlchemyUnitOfWork = Depends(get_request_uow)`` receives the
    SAME instance (FastAPI's dep-dedup), so use cases that re-enter
    ``begin()`` see the already-active session and join the outer
    transaction. The outer ``begin()`` issues
    ``set_config('app.tenant_id', ..., true)`` and
    ``set_config('app.current_user_id', ..., true)`` for RLS — see
    :class:`bootstrap.container._RequestUnitOfWork`.
    """

    uow = build_request_uow()
    async with uow.begin():
        yield uow


async def _load_permissions(role: str, session: object) -> frozenset[str]:
    # The cache loader takes ``session: AsyncSession`` (typed object so the
    # cache stays free of SQLAlchemy imports). The loader runs only on
    # cache miss; concurrent misses serialise on the cache's ``asyncio.Lock``.
    result = await session.execute(  # type: ignore[attr-defined]
        _SELECT_ROLE_PERMISSIONS,
        {"role": role},
    )
    return frozenset(row[0] for row in result.all())


async def current_actor(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> Actor:
    """Resolve the request's :class:`Actor`.

    Raises :class:`InvalidCredentialsError` on a missing
    ``CurrentUserContext`` so the identity-context exception handler can
    render a uniform 401.
    """

    current_user = CurrentUserContext.get()
    if current_user is None:
        raise InvalidCredentialsError("No authenticated user in context")

    tenant_id = TenantContext.get()
    if tenant_id is None:
        return Actor(user_id=current_user.user_id)

    async with uow.begin() as session:
        membership = await session.execute(
            _SELECT_ACTIVE_MEMBER_ROLE,
            {"user_id": current_user.user_id, "tenant_id": tenant_id},
        )
        role_row = membership.scalar_one_or_none()
        if role_row is None:
            # Race: the membership was removed between TenantMiddleware
            # and current_actor. Treat as a fresh 403 — the actor cannot
            # operate inside a tenant they're no longer a member of.
            raise ForbiddenError(missing=["tenant:read"])
        role = str(role_row)
        permissions = await _permission_cache.get(role, lambda r: _load_permissions(r, session))

    return Actor(
        user_id=current_user.user_id,
        tenant_id=tenant_id,
        role=role,
        permissions=permissions,
    )


def require(
    *codes: str,
) -> Callable[..., Awaitable[Actor]]:
    """FastAPI dependency factory — 403s if any code is missing."""

    async def _check(actor: Actor = Depends(current_actor)) -> Actor:
        missing = [c for c in codes if c not in actor.permissions]
        if missing:
            raise ForbiddenError(missing=missing)
        return actor

    return _check


__all__ = ["current_actor", "get_request_uow", "require"]
