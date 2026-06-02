"""Login-attempt throttle port + lockout value object.

Defines the contract every login-attempt throttle adapter (in-memory
for dev/test, Redis for production) implements. The use case calls
``check`` before the password compare to short-circuit when an
identifier or IP has been locked out, ``record_failure`` after a
failed compare, and ``record_success`` after a clean authentication.

Both adapter implementations are intentionally synchronous: the
Redis adapter uses a synchronous client and the use case calls into
the throttle from an ``async`` context via a thin sync call (no
network I/O is awaited at the application boundary).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

LockoutScope = Literal["identifier", "ip", "none"]


@dataclass(frozen=True, slots=True, kw_only=True)
class LockoutState:
    """Result of a throttle ``check``.

    Invariants enforced by the adapters:

    - When ``locked`` is ``True``, ``retry_after_seconds`` is ≥ 1 and
      ``scope`` is one of ``"identifier"`` or ``"ip"``.
    - When ``locked`` is ``False``, ``retry_after_seconds`` is 0 and
      ``scope`` is ``"none"``.
    """

    locked: bool
    retry_after_seconds: int
    scope: LockoutScope


@runtime_checkable
class LoginAttemptThrottle(Protocol):
    def check(self, *, identifier: str, source_ip: str, when: datetime) -> LockoutState: ...

    def record_failure(self, *, identifier: str, source_ip: str, when: datetime) -> None: ...

    def record_success(self, *, identifier: str) -> None: ...


__all__ = ["LockoutScope", "LockoutState", "LoginAttemptThrottle"]
