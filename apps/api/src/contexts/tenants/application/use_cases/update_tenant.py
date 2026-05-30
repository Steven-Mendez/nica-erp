"""``UpdateTenant`` — mutate mutable fiscal metadata (not RUC)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from contexts.tenants.application.ports.outbound import TenantRepository
from contexts.tenants.domain import (
    AuthorizationDgi,
    Municipality,
    Regime,
    Tenant,
    TenantNotFoundError,
)
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class UpdateTenantCommand:
    tenant_id: UUID
    name: str | None = None
    regime: str | None = None
    municipality: str | None = None
    authorization_dgi: AuthorizationDgi | None = None
    fiscal_address: str | None = None
    is_withholder: bool | None = None


@dataclass(slots=True)
class UpdateTenant:
    uow: UnitOfWork
    tenant_repository: TenantRepository
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: UpdateTenantCommand) -> Tenant:
        async with self.uow.begin():
            tenant = await self.tenant_repository.get(command.tenant_id)
            if tenant is None:
                raise TenantNotFoundError(str(command.tenant_id))
            tenant.update_fiscal(
                now=self.now(),
                name=command.name,
                regime=Regime(command.regime) if command.regime else None,  # type: ignore[arg-type]
                municipality=(Municipality(command.municipality) if command.municipality else None),
                authorization_dgi=command.authorization_dgi,
                fiscal_address=command.fiscal_address,
                is_withholder=command.is_withholder,
            )
            await self.tenant_repository.update(tenant)
            return tenant


__all__ = ["UpdateTenant", "UpdateTenantCommand"]
