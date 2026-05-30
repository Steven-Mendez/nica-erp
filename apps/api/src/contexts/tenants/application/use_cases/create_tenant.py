"""``CreateTenant`` — first vertical slice of the tenants context.

Creates the ``Tenant`` aggregate, the owner ``Membership``, and the
matching ``TenantCreated`` outbox row in a single UnitOfWork. The
SPA must follow up with ``POST /v1/tenants/{id}/switch`` to obtain
a JWT carrying ``custom:active_tenant`` for the new tenant.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text

from contexts.tenants.application.ports.outbound import (
    MembershipRepository,
    TenantRepository,
)
from contexts.tenants.domain import (
    AuthorizationDgi,
    Membership,
    Municipality,
    Regime,
    Ruc,
    Tenant,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from shared_kernel.application.outbox import OutboxWriter
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateTenantCommand:
    actor_user_id: UUID
    name: str
    is_withholder: bool = False
    ruc: str | None = None
    regime: str | None = None
    municipality: str | None = None
    authorization_dgi: AuthorizationDgi | None = None
    fiscal_address: str | None = None


@dataclass(frozen=True, slots=True)
class CreateTenantResult:
    tenant_id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class CreateTenant:
    uow: UnitOfWork
    tenant_repository: TenantRepository
    membership_repository: MembershipRepository
    outbox: OutboxWriter
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: CreateTenantCommand) -> CreateTenantResult:
        now = self.now()
        tenant = Tenant.register(
            name=command.name,
            ruc=Ruc.parse(command.ruc) if command.ruc is not None else None,
            regime=Regime(command.regime) if command.regime is not None else None,  # type: ignore[arg-type]
            municipality=Municipality(command.municipality)
            if command.municipality is not None
            else None,
            authorization_dgi=command.authorization_dgi,
            fiscal_address=command.fiscal_address,
            is_withholder=command.is_withholder,
            now=now,
            id_=uuid4(),
        )
        owner = Membership.create_owner(user_id=command.actor_user_id, tenant_id=tenant.id, now=now)
        async with self.uow.begin():
            await self.tenant_repository.add(tenant)
            # Bootstrap path: the caller has no active tenant yet — the
            # ``app.tenant_id`` GUC is the zero-uuid sentinel, which the
            # ``tenant_members_self`` WITH CHECK policy rejects. Re-issue
            # ``set_config('app.tenant_id', new_tenant_id, true)`` so the
            # owner row insert satisfies the policy for the duration of
            # this transaction.
            if isinstance(self.uow, SqlAlchemyUnitOfWork):
                await self.uow.current_session.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"),
                    {"t": str(tenant.id)},
                )
            await self.membership_repository.add(owner)
            for event in tenant.pull_events():
                # TenantCreated emitted via the outbox; payload mirrors the
                # event fields the sprint doc lists.
                if event.__class__.__name__ == "TenantCreated":
                    await self.outbox.append(
                        event_id=event.event_id,
                        event_type="tenants.TenantCreated",
                        event_version=1,
                        aggregate_type="Tenant",
                        aggregate_id=tenant.id,
                        tenant_id=tenant.id,
                        payload={
                            "tenant_id": str(tenant.id),
                            "name": tenant.name,
                            "ruc": tenant.ruc.value if tenant.ruc is not None else None,
                            "municipality": tenant.municipality.value
                            if tenant.municipality is not None
                            else None,
                            "created_at": tenant.created_at.isoformat(),
                        },
                    )
        return CreateTenantResult(
            tenant_id=tenant.id,
            name=tenant.name,
            status=tenant.status,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )


__all__ = ["CreateTenant", "CreateTenantCommand", "CreateTenantResult"]
