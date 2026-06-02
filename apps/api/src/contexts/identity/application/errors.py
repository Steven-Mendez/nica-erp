"""Typed errors raised by identity-context use cases.

Errors are intentionally simple sentinels; the HTTP adapter maps each to a
specific RFC-7807 problem detail with a stable ``code`` field. The application
layer MUST NOT depend on FastAPI exception classes — that's the adapter's job.
"""

from __future__ import annotations

from typing import Literal


class IdentityError(Exception):
    """Base class for identity-context application errors."""


class InvalidCredentialsError(IdentityError):
    """Wrong email/password (or a malformed/invalid token)."""


class TokenExpiredError(IdentityError):
    """The supplied token's ``exp`` claim is in the past."""


class LockoutActiveError(IdentityError):
    """The caller has tripped the per-account lockout window.

    Raised by the identity-provider adapter (e.g. Cognito's built-in
    throttle). Distinct from :class:`AuthLockoutActiveError` which is
    raised by the application-level :class:`LoginAttemptThrottle`
    and additionally carries a ``scope`` so the SPA can choose
    between identifier-level and IP-level copy.
    """

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"Locked out for {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class AuthLockoutActiveError(IdentityError):
    """The application-level login throttle has locked this caller out.

    Raised by ``AuthenticateUseCase`` *before* the password compare
    reaches the identity provider, after the :class:`LoginAttemptThrottle`
    reports a tripped sliding window. The ``scope`` field distinguishes
    identifier-level from IP-level lockouts so the SPA can choose copy.
    """

    def __init__(self, *, retry_after_seconds: int, scope: Literal["identifier", "ip"]) -> None:
        super().__init__(f"Lockout ({scope}) for {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds
        self.scope: Literal["identifier", "ip"] = scope


class SignupEmailNotConfirmedError(IdentityError):
    """The account exists but the email-confirmation step has not completed."""


class EmailSendError(IdentityError):
    """The outbound :class:`EmailSender` adapter failed to deliver."""


class UserNotFoundError(IdentityError):
    """No ``User`` row matches the supplied identifier."""


__all__ = [
    "AuthLockoutActiveError",
    "EmailSendError",
    "IdentityError",
    "InvalidCredentialsError",
    "LockoutActiveError",
    "SignupEmailNotConfirmedError",
    "TokenExpiredError",
    "UserNotFoundError",
]
