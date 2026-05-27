"""``Logout`` use case.

Invalidates every active server-side session via
:meth:`IdentityProvider.global_signout`. The call is idempotent — calling
twice returns ``None`` both times — so SPA double-clicks or replays do not
surface an error. Access tokens already issued REMAIN valid until their
``exp`` per ``docs/06-security-model.md`` §Refresh and revocation.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.ports.outbound import IdentityProvider
from shared_kernel.adapters.context import CurrentUser


@dataclass(frozen=True, slots=True, kw_only=True)
class Logout:
    identity_provider: IdentityProvider

    async def execute(self, *, current_user: CurrentUser) -> None:
        await self.identity_provider.global_signout(external_sub=current_user.external_sub)


__all__ = ["Logout"]
