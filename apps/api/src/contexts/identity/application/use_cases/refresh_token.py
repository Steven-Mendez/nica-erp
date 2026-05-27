"""``RefreshToken`` use case — exchange a refresh token for a new ``Identity``."""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import Identity, IdentityProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshToken:
    identity_provider: IdentityProvider

    async def execute(self, *, refresh_token: str) -> Identity:
        return await self.identity_provider.refresh(refresh_token=refresh_token)


__all__ = ["RefreshToken"]
