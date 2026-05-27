"""``ResendCode`` use case — passthrough to the IdP's resend endpoint."""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class ResendCode:
    identity_provider: IdentityProvider

    async def execute(self, *, email: str) -> None:
        await self.identity_provider.resend_confirmation(email=email)


__all__ = ["ResendCode"]
