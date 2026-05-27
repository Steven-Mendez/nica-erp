"""``Authenticate`` use case — exchange credentials for an ``Identity`` bundle.

Typed errors raised by the IdP adapter (``InvalidCredentialsError``,
``LockoutActiveError``, ``SignupEmailNotConfirmedError``) propagate unchanged
so the HTTP adapter can map them to RFC-7807 problem details.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import Identity, IdentityProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class Authenticate:
    identity_provider: IdentityProvider

    async def execute(self, *, email: str, password: str) -> Identity:
        return await self.identity_provider.authenticate(email=email, password=password)


__all__ = ["Authenticate"]
