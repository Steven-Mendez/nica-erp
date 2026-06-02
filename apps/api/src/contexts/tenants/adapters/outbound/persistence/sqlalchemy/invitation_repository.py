"""SQLAlchemy adapter for :class:`InvitationRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text

from contexts.tenants.domain import Invitation, Role
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_COLUMNS = (
    "id, tenant_id, email, proposed_role, token_hash, expires_at, status, cancelled_at, created_at"
)

# Interpolated columns are trusted; filter values bound as parameters.
_SELECT_BY_ID_SQL = f"SELECT {_COLUMNS} FROM invitations WHERE id = :id"
_SELECT_BY_HASH_SQL = f"SELECT {_COLUMNS} FROM invitations WHERE token_hash = :token_hash"
_SELECT_BY_TENANT_SQL = (
    f"SELECT {_COLUMNS} FROM invitations WHERE tenant_id = :tenant_id ORDER BY created_at DESC"
)
_SELECT_PENDING_BY_EMAIL_SQL = (
    f"SELECT {_COLUMNS} FROM invitations "
    "WHERE tenant_id = :tenant_id AND lower(email) = lower(:email) AND status = 'pending'"
)
_SELECT_BY_ID = text(
    _SELECT_BY_ID_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_BY_HASH = text(
    _SELECT_BY_HASH_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_BY_TENANT = text(
    _SELECT_BY_TENANT_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_PENDING_BY_EMAIL = text(
    _SELECT_PENDING_BY_EMAIL_SQL
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text

_INSERT = text(
    "INSERT INTO invitations ("
    "id, tenant_id, email, proposed_role, token_hash, expires_at, "
    "status, cancelled_at, created_at"
    ") VALUES ("
    ":id, :tenant_id, :email, :proposed_role, :token_hash, :expires_at, "
    ":status, :cancelled_at, :created_at"
    ")"
)

_UPDATE = text(
    "UPDATE invitations SET status = :status, cancelled_at = :cancelled_at WHERE id = :id"
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
                "id": invitation.id,
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
