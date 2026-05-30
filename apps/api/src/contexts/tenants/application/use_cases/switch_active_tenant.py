"""``SwitchActiveTenant`` — update Cognito/Local attribute + mint fresh Identity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.identity.application.ports.outbound import Identity, IdentityProvider
from contexts.tenants.application.ports.outbound import MembershipRepository
from contexts.tenants.domain import NotAMemberError
from shared_kernel.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class SwitchActiveTenantCommand:
    actor_user_id: UUID
    external_sub: str
    target_tenant_id: UUID
    refresh_token: str


@dataclass(slots=True)
class SwitchActiveTenant:
    uow: UnitOfWork
    membership_repository: MembershipRepository
    identity_provider: IdentityProvider

    async def execute(self, command: SwitchActiveTenantCommand) -> Identity:
        async with self.uow.begin():
            membership = await self.membership_repository.find(
                user_id=command.actor_user_id, tenant_id=command.target_tenant_id
            )
            if membership is None or membership.status != "active":
                raise NotAMemberError(str(command.target_tenant_id))
        await self.identity_provider.update_active_tenant(
            external_sub=command.external_sub, tenant_id=str(command.target_tenant_id)
        )
        # Refresh mints fresh tokens that carry the updated attribute.
        return await self.identity_provider.refresh(refresh_token=command.refresh_token)


__all__ = ["SwitchActiveTenant", "SwitchActiveTenantCommand"]
