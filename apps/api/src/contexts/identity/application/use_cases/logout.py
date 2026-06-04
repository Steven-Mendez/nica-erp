"""``Logout`` use case.

Invalidates the caller's refresh token via
:meth:`IdentityProvider.revoke_refresh_token` and (best-effort) the
provider's global sign-out. The call is idempotent — calling twice
returns ``None`` both times — so SPA double-clicks or replays do not
surface an error. Access tokens already issued REMAIN valid until
their ``exp`` per ``docs/06-security-model.md`` §Refresh and revocation.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider
from shared_kernel.adapters.context import CurrentUser


@dataclass(frozen=True, slots=True, kw_only=True)
class Logout:
    identity_provider: IdentityProvider

    async def execute(
        self,
        *,
        current_user: CurrentUser,
        refresh_token: str | None = None,
    ) -> None:
        # Audit F-016: revoke the caller's refresh token's jti so a
        # stolen refresh JWT cannot mint new access tokens after the
        # user signs out. Missing / malformed tokens resolve to a
        # no-op inside the adapter.
        if refresh_token is not None:
            await self.identity_provider.revoke_refresh_token(refresh_token=refresh_token)
        await self.identity_provider.global_signout(external_sub=current_user.external_sub)


__all__ = ["Logout"]
