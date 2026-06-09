"""SQLAlchemy adapter for :class:`TenantRepository`.

Core statements over the shared table metadata against the active UoW
session; the ``Tenant`` aggregate stays free of SQLAlchemy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, bindparam, insert, select, update
from sqlalchemy.exc import IntegrityError

from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tables import tenant_members
from contexts.tenants.domain import (
    AuthorizationDgi,
    FiscalEmail,
    FiscalPhone,
    Municipality,
    Regime,
    Ruc,
    RucCollisionError,
    Tenant,
)
from shared_kernel.adapters.tables import tenants
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_SELECT_BY_ID = select(tenants).where(tenants.c.id == bindparam("id"))
_SELECT_BY_RUC = select(tenants).where(tenants.c.ruc == bindparam("ruc"))
_SELECT_FOR_USER = select(tenants).where(
    tenants.c.id.in_(
        select(tenant_members.c.tenant_id).where(
            tenant_members.c.user_id == bindparam("user_id"),
            tenant_members.c.status == "active",
        )
    )
)

_INSERT = insert(tenants).values(
    id=bindparam("id"),
    name=bindparam("name"),
    ruc=bindparam("ruc"),
    regime=bindparam("regime"),
    departamento=bindparam("departamento"),
    municipality=bindparam("municipality"),
    authorization_dgi_number=bindparam("authorization_dgi_number"),
    authorization_dgi_valid_from=bindparam("authorization_dgi_valid_from"),
    authorization_dgi_valid_to=bindparam("authorization_dgi_valid_to"),
    fiscal_address=bindparam("fiscal_address"),
    fiscal_email=bindparam("fiscal_email"),
    fiscal_phone=bindparam("fiscal_phone"),
    is_withholder=bindparam("is_withholder"),
    status=bindparam("status"),
    created_at=bindparam("created_at"),
    updated_at=bindparam("updated_at"),
)

# ``bindparam("id")`` is reserved inside update() because it names a
# column of the target table; the WHERE param needs the ``b_`` prefix.
_UPDATE = (
    update(tenants)
    .where(tenants.c.id == bindparam("b_id"))
    .values(
        name=bindparam("name"),
        ruc=bindparam("ruc"),
        regime=bindparam("regime"),
        departamento=bindparam("departamento"),
        municipality=bindparam("municipality"),
        authorization_dgi_number=bindparam("authorization_dgi_number"),
        authorization_dgi_valid_from=bindparam("authorization_dgi_valid_from"),
        authorization_dgi_valid_to=bindparam("authorization_dgi_valid_to"),
        fiscal_address=bindparam("fiscal_address"),
        fiscal_email=bindparam("fiscal_email"),
        fiscal_phone=bindparam("fiscal_phone"),
        is_withholder=bindparam("is_withholder"),
        status=bindparam("status"),
        updated_at=bindparam("updated_at"),
    )
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
        try:
            await self._uow.current_session.execute(_INSERT, self._params(tenant))
        except IntegrityError as exc:
            if "uq_tenants_ruc" in str(exc):
                raise RucCollisionError() from exc
            raise

    async def update(self, tenant: Tenant) -> None:
        try:
            await self._uow.current_session.execute(
                _UPDATE, {**self._params(tenant), "b_id": tenant.id}
            )
        except IntegrityError as exc:
            if "uq_tenants_ruc" in str(exc):
                raise RucCollisionError() from exc
            raise

    async def list_for_user(self, user_id: UUID) -> list[Tenant]:
        result = await self._uow.current_session.execute(_SELECT_FOR_USER, {"user_id": user_id})
        return [self._hydrate(row) for row in result.mappings().all()]

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _hydrate(row: RowMapping) -> Tenant:
        # Every fiscal column is nullable. Construct each VO only when
        # the underlying column has a value; otherwise keep None so the
        # aggregate reflects "operator hasn't provided this yet".
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
