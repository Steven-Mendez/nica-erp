"""IdentityProvider outbound port + ``Identity`` result dataclass.

Both the local (database-backed) adapter and the Cognito adapter implement
this Protocol. The eleven methods follow ``docs/06-security-model.md``
§Port methods. Each method is ``async``; each adapter MUST return the same
shape regardless of the underlying IdP so the application layer remains
adapter-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Identity:
    """The result of a successful authentication-style call.

    ``sub`` is the IdP's stable subject identifier (Cognito's ``sub`` claim,
    the local adapter's ``auth_local_users.id`` rendered as a string).
    ``claims`` carries any extra decoded JWT claims the adapter chose to
    surface; callers MUST treat unknown keys as opaque.
    """

    sub: str
    email: str
    access_token: str
    refresh_token: str
    id_token: str
    claims: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class IdentityProvider(Protocol):
    """Outbound port abstracting Cognito and the local DB-backed IdP.

    See ``docs/06-security-model.md`` §Port methods for the canonical list.
    """

    async def register(self, *, email: str, password: str) -> str:
        """Create the IdP-side user record.

        Returns the new external subject. Adapters MUST silently swallow the
        "username already exists" branch (Cognito's ``UsernameExistsException``;
        local's duplicate-email check) so the use case can present a single
        enumeration-resistant response.
        """

    async def authenticate(self, *, email: str, password: str) -> Identity:
        """Exchange credentials for tokens."""

    async def verify_token(self, *, token: str) -> dict[str, Any]:
        """Decode and verify an access token; return its claims.

        Raises on signature/expiry failure.
        """

    async def refresh(self, *, refresh_token: str) -> Identity:
        """Exchange a refresh token for a fresh ``Identity`` bundle."""

    async def confirm_signup(self, *, email: str, code: str) -> str:
        """Confirm the email-verification code; return the external sub."""

    async def resend_confirmation(self, *, email: str) -> None:
        """Re-send the email-verification code."""

    async def forgot_password(self, *, email: str) -> None:
        """Trigger the password-reset email flow.

        Adapters MUST silently swallow the "user does not exist" branch so the
        use case can keep its response enumeration-resistant.
        """

    async def confirm_forgot_password(self, *, email: str, code: str, new_password: str) -> None:
        """Apply the reset using the code emailed by :meth:`forgot_password`."""

    async def change_password(
        self, *, access_token: str, old_password: str, new_password: str
    ) -> None:
        """Rotate the caller's password while authenticated."""

    async def global_signout(self, *, external_sub: str) -> None:
        """Invalidate every active session for ``external_sub``. Idempotent."""

    async def update_active_tenant(self, *, external_sub: str, tenant_id: str) -> None:
        """Persist the caller's chosen tenant onto the IdP record."""


__all__ = ["Identity", "IdentityProvider"]
