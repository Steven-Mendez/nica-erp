"""``ConfirmSignup`` use case.

Confirms the email-verification code via the IdP, then atomically:
1. constructs and persists the ``User`` aggregate, and
2. writes the resulting ``identity.UserRegistered v1`` event to the outbox.

A single ``UnitOfWork.begin()`` covers both side effects so either both
commit or both roll back.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from contexts.identity.application.constants import SYSTEM_GLOBAL_TENANT_ID
from contexts.identity.application.ports.outbound import (
    Identity,
    IdentityProvider,
    UserRepository,
)
from contexts.identity.domain import Email, User, UserRegistered
from contexts.identity.domain.events import (
    IDENTITY_USER_REGISTERED_EVENT_TYPE,
    IDENTITY_USER_REGISTERED_EVENT_VERSION,
)
from shared_kernel.application.outbox import OutboxWriter
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfirmSignup:
    identity_provider: IdentityProvider
    user_repository: UserRepository
    outbox_writer: OutboxWriter
    uow: UnitOfWork
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(
        self, *, email: str, code: str, password: str | None = None
    ) -> Identity | None:
        external_sub = await self.identity_provider.confirm_signup(email=email, code=code)
        email_vo = Email.parse(email)
        now = self.now()
        async with self.uow.begin():
            user = User.register(external_sub=external_sub, email=email_vo, now=now)
            await self.user_repository.add(user)
            for event in user.pull_events():
                assert isinstance(event, UserRegistered)  # narrow for mypy
                await self.outbox_writer.append(
                    event_id=event.event_id,
                    event_type=IDENTITY_USER_REGISTERED_EVENT_TYPE,
                    event_version=IDENTITY_USER_REGISTERED_EVENT_VERSION,
                    aggregate_type="User",
                    aggregate_id=user.id,
                    tenant_id=SYSTEM_GLOBAL_TENANT_ID,
                    payload={
                        "user_id": str(event.user_id),
                        "email": event.email,
                        "registered_at": event.registered_at.isoformat(),
                    },
                )
        if password is None:
            return None
        # The aggregate + outbox event are committed before authenticating,
        # so a bad password leaves the user persisted and the caller can
        # retry via POST /v1/auth/login without re-entering the email code.
        return await self.identity_provider.authenticate(email=email, password=password)


__all__ = ["ConfirmSignup"]
