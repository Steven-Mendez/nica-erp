"""``AcceptInvitation`` — public route that flips a pending invitation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text

from contexts.identity.application.ports.outbound import Identity, IdentityProvider
from contexts.tenants.application.ports.outbound import (
    InvitationRepository,
    InvitationTokenGenerator,
    MembershipRepository,
)
from contexts.tenants.domain import (
    InvitationInvalidError,
    InvitationNotFoundError,
    Membership,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from shared_kernel.application.outbox import OutboxWriter
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AcceptInvitationCommand:
    token: str
    user_id: UUID  # taken from CurrentUserContext at the HTTP layer
    external_sub: str  # idem; required for IdP rotation calls
    prior_active_tenant: str | None  # validated from JWT, not request body
    refresh_token: str | None  # optional; rotation skipped when absent


@dataclass(frozen=True, slots=True)
class AcceptInvitationResult:
    tenant_id: UUID
    role: str
    tokens: Identity | None = None


@dataclass(slots=True)
class AcceptInvitation:
    uow: UnitOfWork
    invitation_repository: InvitationRepository
    membership_repository: MembershipRepository
    token_generator: InvitationTokenGenerator
    outbox: OutboxWriter
    identity_provider: IdentityProvider
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(self, command: AcceptInvitationCommand) -> AcceptInvitationResult:
        # Verify signature first — cheap and reveals nothing about the DB.
        try:
            claims = self.token_generator.verify(token=command.token)
        except Exception as exc:
            raise InvitationInvalidError(str(exc)) from exc
        token_hash = self.token_generator.hash(token=command.token)
        async with self.uow.begin():
            # ``/v1/invitations/accept`` is on the no-tenant-required
            # allowlist, so ``TenantContext`` is unset and the request
            # UoW opens the transaction with ``app.tenant_id`` pinned
            # to the zero-uuid sentinel. Per-tenant RLS on
            # ``invitations`` would then filter the row out. Re-issue
            # ``set_config('app.tenant_id', ..., true)`` from the
            # verified token claim so the invitation row, the new
            # membership insert (WITH CHECK) and the outbox row all
            # observe the same tenant for the rest of this transaction.
            if isinstance(self.uow, SqlAlchemyUnitOfWork):
                await self.uow.current_session.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"),
                    {"t": str(claims.tenant_id)},
                )
            invitation = await self.invitation_repository.get_by_token_hash(token_hash)
            if invitation is None:
                raise InvitationNotFoundError(token_hash)
            invitation.accept(now=self.now())
            membership = Membership.join(
                user_id=command.user_id,
                tenant_id=invitation.tenant_id,
                role=invitation.proposed_role,
                now=self.now(),
            )
            await self.membership_repository.add(membership)
            await self.invitation_repository.update(invitation)
            await self.outbox.append(
                event_id=uuid4(),
                event_type="tenants.MemberJoined",
                event_version=1,
                aggregate_type="Membership",
                aggregate_id=membership.id,
                tenant_id=invitation.tenant_id,
                payload={
                    "tenant_id": str(invitation.tenant_id),
                    "user_id": str(membership.user_id),
                    "role": membership.role.value,
                    "joined_at": membership.joined_at.isoformat(),
                },
            )
        tokens: Identity | None = None
        # Rotate the session only for first-membership invitees who
        # supplied a refresh token. Veteran callers (those already
        # bound to an empresa) keep their current active tenant so a
        # second-empresa invitation does not silently switch them.
        if command.prior_active_tenant is None and command.refresh_token is not None:
            await self.identity_provider.update_active_tenant(
                external_sub=command.external_sub,
                tenant_id=str(invitation.tenant_id),
            )
            tokens = await self.identity_provider.refresh(refresh_token=command.refresh_token)
        return AcceptInvitationResult(
            tenant_id=invitation.tenant_id,
            role=membership.role.value,
            tokens=tokens,
        )


__all__ = ["AcceptInvitation", "AcceptInvitationCommand", "AcceptInvitationResult"]
