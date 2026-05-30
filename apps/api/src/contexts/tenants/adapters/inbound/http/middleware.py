"""Tenant middleware — validates membership and sets ``TenantContext``.

Runs **after** :class:`AuthMiddleware` (which populates
``CurrentUserContext``) and **before** the route layer (which depends on
``current_actor`` to materialise the request's :class:`Actor`).

The middleware skips the unauthenticated allowlist (those routes never
need a tenant) and the no-tenant-required allowlist (``POST /v1/tenants``,
``GET /v1/me``, etc.). For everything else, it:

1. Reads the JWT-claimed ``active_tenant`` from ``CurrentUserContext``.
2. If the claim is missing, ``AuthMiddleware`` already returned 403
   ``tenant.required``; the middleware should never see that branch.
3. Opens a short read-only UoW (which issues
   ``set_config('app.current_user_id', :u, true)`` via the
   ``_RequestUnitOfWork.begin()`` hook) and looks up the
   ``tenant_members`` row.
4. On miss → 403 ``tenant.not_member``.
5. On hit → ``TenantContext.set(tenant_id)`` for downstream code, and
   pass through.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from contexts.identity.adapters.inbound.http.allowlist import (
    is_no_tenant_required,
    is_unauthenticated,
)
from contexts.identity.adapters.inbound.http.errors import PROBLEM_CONTENT_TYPE
from contexts.identity.adapters.inbound.http.schemas import ProblemDetail
from shared_kernel.adapters.context import CurrentUserContext, TenantContext
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


def _problem_response(status: int, code: str, title: str, **extra: Any) -> JSONResponse:
    problem = ProblemDetail(status=status, code=code, title=title, **extra)
    return JSONResponse(
        content=problem.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
    )


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve the active tenant and pin it to :class:`TenantContext`."""

    def __init__(
        self,
        app: Any,
        *,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        is_unauthenticated_fn: Callable[[str, str], bool] = is_unauthenticated,
        is_no_tenant_required_fn: Callable[[str, str], bool] = is_no_tenant_required,
    ) -> None:
        super().__init__(app)
        self._uow_factory = uow_factory
        self._is_unauthenticated = is_unauthenticated_fn
        self._is_no_tenant_required = is_no_tenant_required_fn

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method.upper()
        path = request.url.path

        if self._is_unauthenticated(method, path):
            return await call_next(request)

        current_user = CurrentUserContext.get()
        if current_user is None:
            # AuthMiddleware short-circuited; this branch is defensive — the
            # middleware ordering in bootstrap/api.py guarantees Auth runs
            # first and returns 401 on a missing user.
            return _problem_response(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail="No authenticated user in context",
            )

        if current_user.active_tenant is None:
            # AuthMiddleware also enforces the no-tenant-required allowlist;
            # this branch trusts that and passes through without setting
            # TenantContext.
            return await call_next(request)

        try:
            tenant_uuid = UUID(current_user.active_tenant)
        except (ValueError, AttributeError):
            return _problem_response(
                403,
                "tenant.not_member",
                "Not a member of the requested tenant",
                detail="Active tenant claim is not a UUID",
            )

        # Membership check — runs through the ``tenant_members_self`` RLS
        # policy, which allows the read on the OR-branch
        # (``user_id = app.current_user_id``) regardless of whether
        # ``app.tenant_id`` matches the claim. So a forged JWT cannot
        # bypass: the query returns zero rows because no membership exists.
        uow = self._uow_factory()
        async with uow.begin() as session:
            result = await session.execute(
                text(
                    "SELECT 1 FROM tenant_members "
                    "WHERE user_id = :user_id "
                    "  AND tenant_id = :tenant_id "
                    "  AND status = 'active' "
                    "LIMIT 1"
                ),
                {"user_id": current_user.user_id, "tenant_id": tenant_uuid},
            )
            hit = result.scalar_one_or_none()
        if hit is None:
            return _problem_response(
                403,
                "tenant.not_member",
                "Not a member of the requested tenant",
                detail=f"User is not an active member of tenant {tenant_uuid}",
            )

        TenantContext.set(tenant_uuid)
        try:
            return await call_next(request)
        finally:
            TenantContext.clear()


__all__ = ["TenantMiddleware"]
