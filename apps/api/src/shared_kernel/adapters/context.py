"""Request-scoped tenant + current-user context vars.

HTTP middleware sets these once per request from the JWT and the resolved
tenant; downstream code reads them via `TenantContext.get()` /
`CurrentUserContext.get()` instead of threading them through every call.
The tenant value is also issued to Postgres as `SET LOCAL app.tenant_id`
so row-level security policies see it.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: UUID
    email: str
    external_sub: str
    active_tenant: str | None = None


_tenant_id: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)
_current_user: ContextVar[CurrentUser | None] = ContextVar("current_user", default=None)


class TenantContext:
    @staticmethod
    def get() -> UUID | None:
        return _tenant_id.get()

    @staticmethod
    def set(tenant_id: UUID) -> None:
        _tenant_id.set(tenant_id)

    @staticmethod
    def clear() -> None:
        _tenant_id.set(None)


class CurrentUserContext:
    @staticmethod
    def get() -> CurrentUser | None:
        return _current_user.get()

    @staticmethod
    def set(user: CurrentUser) -> None:
        _current_user.set(user)

    @staticmethod
    def clear() -> None:
        _current_user.set(None)
