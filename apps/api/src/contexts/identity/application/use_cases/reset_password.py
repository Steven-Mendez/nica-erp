"""``ResetPassword`` use case — apply the code from ``ForgotPassword``.

Re-validates the new password policy locally before delegating to the IdP.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider
from contexts.identity.domain import Password


@dataclass(frozen=True, slots=True, kw_only=True)
class ResetPassword:
    identity_provider: IdentityProvider

    async def execute(self, *, email: str, code: str, new_password: str) -> None:
        Password(value=new_password).validate_policy()
        await self.identity_provider.confirm_forgot_password(
            email=email, code=code, new_password=new_password
        )


__all__ = ["ResetPassword"]
