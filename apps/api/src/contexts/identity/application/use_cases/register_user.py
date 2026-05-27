"""``RegisterUser`` use case.

Validates the email shape and password policy locally before delegating to
the :class:`IdentityProvider`. The adapter is responsible for swallowing the
"username already exists" branch so the response shape is enumeration-
resistant.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider
from contexts.identity.domain import Email, Password


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisterUser:
    identity_provider: IdentityProvider

    async def execute(self, *, email: str, password: str) -> None:
        Email.parse(email)
        Password(value=password).validate_policy()
        await self.identity_provider.register(email=email, password=password)


__all__ = ["RegisterUser"]
