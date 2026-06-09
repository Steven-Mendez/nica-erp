"""SQLAlchemy adapter for :class:`InvitationRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, Text, bindparam, func, insert, select, update

from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tables import invitations
from contexts.tenants.domain import Invitation, Role
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_t = invitations

_SELECT_BY_ID = select(_t).where(_t.c.id == bindparam("id"))
_SELECT_BY_HASH = select(_t).where(_t.c.token_hash == bindparam("token_hash"))
_SELECT_BY_TENANT = (
    select(_t).where(_t.c.tenant_id == bindparam("tenant_id")).order_by(_t.c.created_at.desc())
)
# ``lower(email) = lower(:email)`` must stay verbatim — the pending
# lookup's partial expression index matches exactly that predicate.
# The bindparam is typed explicitly so lower() does not leave the
# driver guessing the parameter type.
_SELECT_PENDING_BY_EMAIL = select(_t).where(
    _t.c.tenant_id == bindparam("tenant_id"),
    func.lower(_t.c.email) == func.lower(bindparam("email", type_=Text())),
    _t.c.status == "pending",
)

_INSERT = insert(_t).values(
    id=bindparam("id"),
    tenant_id=bindparam("tenant_id"),
    email=bindparam("email"),
    proposed_role=bindparam("proposed_role"),
    token_hash=bindparam("token_hash"),
    expires_at=bindparam("expires_at"),
    status=bindparam("status"),
    cancelled_at=bindparam("cancelled_at"),
    created_at=bindparam("created_at"),
)

# ``bindparam("id")`` is reserved inside update() because it names a
# column of the target table; the WHERE param needs the ``b_`` prefix.
_UPDATE = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(status=bindparam("status"), cancelled_at=bindparam("cancelled_at"))
)


class InvitationRepositorySqlAlchemy:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def add(self, invitation: Invitation) -> None:
        await self._uow.current_session.execute(_INSERT, self._params(invitation))

    async def update(self, invitation: Invitation) -> None:
        await self._uow.current_session.execute(
            _UPDATE,
            {
                "b_id": invitation.id,
                "status": invitation.status,
                "cancelled_at": invitation.cancelled_at,
            },
        )

    async def get(self, invitation_id: UUID) -> Invitation | None:
        result = await self._uow.current_session.execute(_SELECT_BY_ID, {"id": invitation_id})
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        result = await self._uow.current_session.execute(
            _SELECT_BY_HASH, {"token_hash": token_hash}
        )
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[Invitation]:
        result = await self._uow.current_session.execute(
            _SELECT_BY_TENANT, {"tenant_id": tenant_id}
        )
        return [self._hydrate(row) for row in result.mappings().all()]

    async def list_pending_by_email(self, tenant_id: UUID, email: str) -> list[Invitation]:
        result = await self._uow.current_session.execute(
            _SELECT_PENDING_BY_EMAIL, {"tenant_id": tenant_id, "email": email}
        )
        return [self._hydrate(row) for row in result.mappings().all()]

    @staticmethod
    def _hydrate(row: RowMapping) -> Invitation:
        return Invitation(
            id=row["id"],
            tenant_id=row["tenant_id"],
            email=row["email"],
            proposed_role=Role(row["proposed_role"]),
            token_hash=row["token_hash"],
            expires_at=_as_dt(row["expires_at"]),
            status=row["status"],
            cancelled_at=(_as_dt(row["cancelled_at"]) if row["cancelled_at"] is not None else None),
            created_at=_as_dt(row["created_at"]),
        )

    @staticmethod
    def _params(invitation: Invitation) -> dict[str, Any]:
        return {
            "id": invitation.id,
            "tenant_id": invitation.tenant_id,
            "email": invitation.email,
            "proposed_role": invitation.proposed_role.value,
            "token_hash": invitation.token_hash,
            "expires_at": invitation.expires_at,
            "status": invitation.status,
            "cancelled_at": invitation.cancelled_at,
            "created_at": invitation.created_at,
        }


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError(f"Expected datetime, got {type(value).__name__}")


__all__ = ["InvitationRepositorySqlAlchemy"]
