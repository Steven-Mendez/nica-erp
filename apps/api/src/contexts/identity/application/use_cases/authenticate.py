"""``Authenticate`` use case — exchange credentials for an ``Identity`` bundle.

Wraps the identity-provider call in a :class:`LoginAttemptThrottle`
sliding-window: the use case calls ``check`` first to short-circuit
locked identifiers/IPs before any password comparison reaches the
identity provider, then ``record_failure`` on a wrong-credentials
exception and ``record_success`` on a clean authentication.

Typed errors raised by the IdP adapter (``InvalidCredentialsError``,
``LockoutActiveError``, ``SignupEmailNotConfirmedError``) propagate
unchanged so the HTTP adapter can map them to RFC-7807 problem
details. The application-level lockout has its own error type
(:class:`AuthLockoutActiveError`) so the HTTP adapter can distinguish it
from the provider-level lockout and map to 429 + ``Retry-After``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from contexts.identity.application.errors import (
    AuthLockoutActiveError,
    InvalidCredentialsError,
)
from contexts.identity.application.login_attempt_throttle import (
    LoginAttemptThrottle,
)
from contexts.identity.application.ports.outbound import Identity, IdentityProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class Authenticate:
    identity_provider: IdentityProvider
    throttle: LoginAttemptThrottle
    source_ip: str

    async def execute(self, *, email: str, password: str) -> Identity:
        when = datetime.now(UTC)
        state = self.throttle.check(identifier=email, source_ip=self.source_ip, when=when)
        if state.locked:
            # Narrow ``scope`` so the type checker accepts the kwarg —
            # ``check`` only ever returns ``"identifier"`` or ``"ip"``
            # when ``locked`` is True (the "none" variant is paired
            # with ``locked=False`` by adapter invariant).
            assert state.scope in ("identifier", "ip")
            raise AuthLockoutActiveError(
                retry_after_seconds=state.retry_after_seconds,
                scope=state.scope,
            )
        try:
            identity = await self.identity_provider.authenticate(email=email, password=password)
        except InvalidCredentialsError:
            # Record the failure *after* the IdP responds so a transient
            # IdP outage doesn't accumulate against the operator. The
            # `when` snapshot was taken before the call so the timestamp
            # is monotonic with the ``check`` above.
            self.throttle.record_failure(identifier=email, source_ip=self.source_ip, when=when)
            raise
        self.throttle.record_success(identifier=email)
        return identity


__all__ = ["Authenticate"]
