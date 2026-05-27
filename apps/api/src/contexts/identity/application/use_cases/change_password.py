"""``ChangePassword`` use case.

Re-validates the password policy locally so the caller gets a deterministic
error before the adapter network call is made.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider
from contexts.identity.domain import Password


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePassword:
    identity_provider: IdentityProvider

    async def execute(self, *, access_token: str, old_password: str, new_password: str) -> None:
        Password(value=new_password).validate_policy()
        await self.identity_provider.change_password(
            access_token=access_token,
            old_password=old_password,
            new_password=new_password,
        )


__all__ = ["ChangePassword"]
