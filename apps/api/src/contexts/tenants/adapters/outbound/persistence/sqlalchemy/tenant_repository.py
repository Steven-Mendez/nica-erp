"""SQLAlchemy adapter for :class:`TenantRepository`.

Raw SQL via :func:`sqlalchemy.text` against the active UoW session;
the ``Tenant`` aggregate stays free of SQLAlchemy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text

from contexts.tenants.domain import (
    AuthorizationDgi,
    FiscalEmail,
    FiscalPhone,
    Municipality,
    Regime,
    Ruc,
    Tenant,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_COLUMNS = (
    "id, name, ruc, regime, departamento, municipality, "
    "authorization_dgi_number, authorization_dgi_valid_from, "
    "authorization_dgi_valid_to, fiscal_address, fiscal_email, "
    "fiscal_phone, is_withholder, status, created_at, updated_at"
)

# The SQL strings below interpolate only the trusted module-level
# `_COLUMNS` constant — no user input reaches the SQL. Filter values are
# bound via `:param` placeholders, which SQLAlchemy escapes through the
# driver. Building each SQL string before passing it to ``text()`` keeps
# every ``text(...)`` call on a single line so the per-call
# ``# nosemgrep`` suppressor is unambiguous.
_SELECT_BY_ID_SQL = f"SELECT {_COLUMNS} FROM tenants WHERE id = :id"
_SELECT_BY_RUC_SQL = f"SELECT {_COLUMNS} FROM tenants WHERE ruc = :ruc"
_SELECT_FOR_USER_SQL = (
    f"SELECT {_COLUMNS} FROM tenants WHERE id IN ("
    " SELECT tenant_id FROM tenant_members"
    " WHERE user_id = :user_id AND status = 'active'"
    ")"
)
# nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_BY_ID = text(_SELECT_BY_ID_SQL)
# nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_BY_RUC = text(_SELECT_BY_RUC_SQL)
# nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
_SELECT_FOR_USER = text(_SELECT_FOR_USER_SQL)

_INSERT = text(
    "INSERT INTO tenants ("
    "id, name, ruc, regime, departamento, municipality, "
    "authorization_dgi_number, authorization_dgi_valid_from, "
    "authorization_dgi_valid_to, fiscal_address, fiscal_email, "
    "fiscal_phone, is_withholder, status, created_at, updated_at"
    ") VALUES ("
    ":id, :name, :ruc, :regime, :departamento, :municipality, "
    ":authorization_dgi_number, :authorization_dgi_valid_from, "
    ":authorization_dgi_valid_to, :fiscal_address, :fiscal_email, "
    ":fiscal_phone, :is_withholder, :status, :created_at, :updated_at"
    ")"
)

_UPDATE = text(
    "UPDATE tenants SET "
    "name = :name, "
    "ruc = :ruc, "
    "regime = :regime, "
    "departamento = :departamento, "
    "municipality = :municipality, "
    "authorization_dgi_number = :authorization_dgi_number, "
    "authorization_dgi_valid_from = :authorization_dgi_valid_from, "
    "authorization_dgi_valid_to = :authorization_dgi_valid_to, "
    "fiscal_address = :fiscal_address, "
    "fiscal_email = :fiscal_email, "
    "fiscal_phone = :fiscal_phone, "
    "is_withholder = :is_withholder, "
    "status = :status, "
    "updated_at = :updated_at "
    "WHERE id = :id"
)


class TenantRepositorySqlAlchemy:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def get(self, tenant_id: UUID) -> Tenant | None:
        result = await self._uow.current_session.execute(_SELECT_BY_ID, {"id": tenant_id})
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def get_by_ruc(self, ruc: str) -> Tenant | None:
        result = await self._uow.current_session.execute(_SELECT_BY_RUC, {"ruc": ruc})
        row = result.mappings().one_or_none()
        return self._hydrate(row) if row is not None else None

    async def add(self, tenant: Tenant) -> None:
        await self._uow.current_session.execute(_INSERT, self._params(tenant))

    async def update(self, tenant: Tenant) -> None:
        await self._uow.current_session.execute(_UPDATE, self._params(tenant))

    async def list_for_user(self, user_id: UUID) -> list[Tenant]:
        result = await self._uow.current_session.execute(_SELECT_FOR_USER, {"user_id": user_id})
        return [self._hydrate(row) for row in result.mappings().all()]

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _hydrate(row: RowMapping) -> Tenant:
        # Per ADR-0034, every fiscal column is nullable. Construct each VO
        # only when the underlying column has a value; otherwise keep None
        # so the aggregate reflects "operator hasn't provided this yet".
        dgi_number = row["authorization_dgi_number"]
        dgi_from = row["authorization_dgi_valid_from"]
        dgi_to = row["authorization_dgi_valid_to"]
        authorization_dgi = (
            AuthorizationDgi(number=dgi_number, valid_from=dgi_from, valid_to=dgi_to)
            if dgi_number is not None and dgi_from is not None and dgi_to is not None
            else None
        )
        return Tenant(
            id_=row["id"],
            name=row["name"],
            ruc=Ruc(row["ruc"]) if row["ruc"] is not None else None,
            regime=Regime(row["regime"]) if row["regime"] is not None else None,
            departamento=row["departamento"],
            municipality=Municipality(row["municipality"])
            if row["municipality"] is not None
            else None,
            authorization_dgi=authorization_dgi,
            fiscal_address=row["fiscal_address"],
            fiscal_email=FiscalEmail(row["fiscal_email"])
            if row["fiscal_email"] is not None
            else None,
            fiscal_phone=FiscalPhone(row["fiscal_phone"])
            if row["fiscal_phone"] is not None
            else None,
            is_withholder=bool(row["is_withholder"]),
            status=row["status"],
            created_at=_as_dt(row["created_at"]),
            updated_at=_as_dt(row["updated_at"]),
        )

    @staticmethod
    def _params(tenant: Tenant) -> dict[str, Any]:
        dgi = tenant.authorization_dgi
        return {
            "id": tenant.id,
            "name": tenant.name,
            "ruc": tenant.ruc.value if tenant.ruc is not None else None,
            "regime": tenant.regime.value if tenant.regime is not None else None,
            "departamento": tenant.departamento,
            "municipality": tenant.municipality.value if tenant.municipality is not None else None,
            "authorization_dgi_number": dgi.number if dgi is not None else None,
            "authorization_dgi_valid_from": dgi.valid_from if dgi is not None else None,
            "authorization_dgi_valid_to": dgi.valid_to if dgi is not None else None,
            "fiscal_address": tenant.fiscal_address,
            "fiscal_email": tenant.fiscal_email.value if tenant.fiscal_email is not None else None,
            "fiscal_phone": tenant.fiscal_phone.value if tenant.fiscal_phone is not None else None,
            "is_withholder": tenant.is_withholder,
            "status": tenant.status,
            "created_at": tenant.created_at,
            "updated_at": tenant.updated_at,
        }


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError(f"Expected datetime, got {type(value).__name__}")


__all__ = ["TenantRepositorySqlAlchemy"]
