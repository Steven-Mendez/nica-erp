"""``ForgotPassword`` use case — passthrough.

Adapters swallow the "user does not exist" branch so the HTTP response shape
is enumeration-resistant.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class ForgotPassword:
    identity_provider: IdentityProvider

    async def execute(self, *, email: str) -> None:
        await self.identity_provider.forgot_password(email=email)


__all__ = ["ForgotPassword"]
