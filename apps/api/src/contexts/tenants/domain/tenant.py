"""``Tenant`` aggregate root."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from contexts.tenants.domain.authorization_dgi import AuthorizationDgi
from contexts.tenants.domain.events import TenantCreated
from contexts.tenants.domain.municipality import Municipality
from contexts.tenants.domain.regime import Regime
from contexts.tenants.domain.ruc import Ruc
from shared_kernel.domain.aggregate import AggregateRoot

TenantStatus = Literal["provisioning", "active", "suspended", "purged"]


class Tenant(AggregateRoot[UUID]):
    """Tenant root — fiscal metadata + lifecycle status.

    Per ADR-0034, every fiscal field is optional at creation time.
    The aggregate stores ``None`` until the operator fills in the
    real value via a future edit flow. The value objects themselves
    stay strict — they only run validation when constructed.
    """

    __slots__ = (
        "_authorization_dgi",
        "_created_at",
        "_fiscal_address",
        "_is_withholder",
        "_municipality",
        "_name",
        "_regime",
        "_ruc",
        "_status",
        "_updated_at",
    )

    def __init__(
        self,
        id_: UUID,
        *,
        name: str,
        ruc: Ruc | None,
        regime: Regime | None,
        municipality: Municipality | None,
        authorization_dgi: AuthorizationDgi | None,
        fiscal_address: str | None,
        is_withholder: bool,
        status: TenantStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id_)
        self._name = name
        self._ruc = ruc
        self._regime = regime
        self._municipality = municipality
        self._authorization_dgi = authorization_dgi
        self._fiscal_address = fiscal_address
        self._is_withholder = is_withholder
        self._status = status
        self._created_at = created_at
        self._updated_at = updated_at

    # Factories ---------------------------------------------------------------
    @classmethod
    def register(
        cls,
        *,
        name: str,
        is_withholder: bool,
        now: datetime,
        ruc: Ruc | None = None,
        regime: Regime | None = None,
        municipality: Municipality | None = None,
        authorization_dgi: AuthorizationDgi | None = None,
        fiscal_address: str | None = None,
        id_: UUID | None = None,
    ) -> Tenant:
        tenant_id = id_ or uuid4()
        tenant = cls(
            tenant_id,
            name=name,
            ruc=ruc,
            regime=regime,
            municipality=municipality,
            authorization_dgi=authorization_dgi,
            fiscal_address=fiscal_address,
            is_withholder=is_withholder,
            status="active",
            created_at=now,
            updated_at=now,
        )
        tenant._record(
            TenantCreated(
                tenant_id=tenant_id,
                name=name,
                ruc=ruc.value if ruc is not None else None,
                municipality=municipality.value if municipality is not None else None,
                created_at=now,
            )
        )
        return tenant

    # Mutations ---------------------------------------------------------------
    def update_fiscal(
        self,
        *,
        now: datetime,
        name: str | None = None,
        regime: Regime | None = None,
        municipality: Municipality | None = None,
        authorization_dgi: AuthorizationDgi | None = None,
        fiscal_address: str | None = None,
        is_withholder: bool | None = None,
    ) -> None:
        # RUC immutability is enforced by signature: this method does NOT
        # accept a ruc keyword. Callers attempting to pass `ruc=` get a
        # `TypeError` from Python's keyword-only contract.
        if name is not None:
            self._name = name
        if regime is not None:
            self._regime = regime
        if municipality is not None:
            self._municipality = municipality
        if authorization_dgi is not None:
            self._authorization_dgi = authorization_dgi
        if fiscal_address is not None:
            self._fiscal_address = fiscal_address
        if is_withholder is not None:
            self._is_withholder = is_withholder
        self._updated_at = now

    # Read-only accessors -----------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    @property
    def ruc(self) -> Ruc | None:
        return self._ruc

    @property
    def regime(self) -> Regime | None:
        return self._regime

    @property
    def municipality(self) -> Municipality | None:
        return self._municipality

    @property
    def authorization_dgi(self) -> AuthorizationDgi | None:
        return self._authorization_dgi

    @property
    def fiscal_address(self) -> str | None:
        return self._fiscal_address

    @property
    def is_withholder(self) -> bool:
        return self._is_withholder

    @property
    def status(self) -> TenantStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at


__all__ = ["Tenant", "TenantStatus"]
