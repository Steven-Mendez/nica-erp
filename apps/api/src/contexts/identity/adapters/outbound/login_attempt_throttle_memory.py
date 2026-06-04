"""In-memory login-attempt throttle adapter.

Used by the local-dev and unit/integration test profiles where a Redis
server would be heavy-weight. Stores failure timestamps in two
``deque``s — one per identifier, one per source IP — and prunes them
to the configured sliding window on every call. Thread-safe via a
single coarse lock; the throughput cost is acceptable at the volumes
this adapter sees (test suites, single-process dev server).

Identifier-scope lockouts escalate exponentially per audit F-023:
3 → 30 → 300 → 1800 seconds across consecutive lockout cycles. The
counter resets on a successful login. IP-scope keeps a fixed 600-second
``retry_after_seconds`` once 20 failures fall inside the 10-minute
window.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

from contexts.identity.application.login_attempt_throttle import (
    LockoutState,
    LoginAttemptThrottle,
)

# Backoff schedule (seconds) indexed by consecutive_lockouts - 1.
# Beyond the last entry the lockout remains at the final tier until a
# successful login resets the counter.
_IDENTIFIER_BACKOFF_SCHEDULE: tuple[int, ...] = (3, 30, 300, 1800)
_IP_LOCKOUT_SECONDS = 600


class InMemoryLoginAttemptThrottle(LoginAttemptThrottle):
    """Sliding-window throttle with two independent counters per call.

    The identifier and IP windows are deliberately distinct: a single
    operator typing the wrong password 5 times locks the identifier,
    while a credential-stuffing IP that cycles 20 different identifiers
    locks the IP regardless of which identifiers it targets.
    """

    def __init__(
        self,
        *,
        identifier_limit: int = 5,
        identifier_window: timedelta = timedelta(minutes=15),
        ip_limit: int = 20,
        ip_window: timedelta = timedelta(minutes=10),
    ) -> None:
        if identifier_limit < 1 or ip_limit < 1:
            raise ValueError("limits must be >= 1")
        self._identifier_limit = identifier_limit
        self._identifier_window = identifier_window
        self._ip_limit = ip_limit
        self._ip_window = ip_window
        self._identifier_hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._ip_hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._consecutive_lockouts: dict[str, int] = defaultdict(int)
        self._lockout_until: dict[str, datetime] = {}
        self._lock = Lock()

    # ---- LoginAttemptThrottle Protocol --------------------------------

    def check(self, *, identifier: str, source_ip: str, when: datetime) -> LockoutState:
        identifier_key = self._normalise_identifier(identifier)
        with self._lock:
            # Honour any active identifier lockout from the previous
            # threshold trip; the rolling window only counts the
            # failures inside the *current* cycle, not the historical
            # ones that already triggered a lock.
            locked_until = self._lockout_until.get(identifier_key)
            if locked_until is not None and locked_until > when:
                seconds = max(int((locked_until - when).total_seconds()), 1)
                return LockoutState(
                    locked=True,
                    retry_after_seconds=seconds,
                    scope="identifier",
                )
            self._prune_locked(identifier_key, source_ip, when)
            identifier_count = len(self._identifier_hits.get(identifier_key, ()))
            ip_count = len(self._ip_hits.get(source_ip, ()))
            # Identifier wins ties — it's the more specific signal.
            if identifier_count >= self._identifier_limit:
                # Escalate to the next backoff tier.
                self._consecutive_lockouts[identifier_key] += 1
                tier = min(
                    self._consecutive_lockouts[identifier_key],
                    len(_IDENTIFIER_BACKOFF_SCHEDULE),
                )
                seconds = _IDENTIFIER_BACKOFF_SCHEDULE[tier - 1]
                self._lockout_until[identifier_key] = when + timedelta(seconds=seconds)
                # Reset the in-window failure counter so the next cycle
                # starts fresh; the consecutive-lockouts counter
                # remembers the escalation across cycles.
                self._identifier_hits.pop(identifier_key, None)
                return LockoutState(
                    locked=True,
                    retry_after_seconds=seconds,
                    scope="identifier",
                )
            if ip_count >= self._ip_limit:
                # IP-scope lockout: fixed 10-minute window per audit
                # F-023, so the SPA / Spanish copy can show a stable
                # 600-second wait regardless of when in the window
                # the threshold was crossed.
                return LockoutState(
                    locked=True,
                    retry_after_seconds=_IP_LOCKOUT_SECONDS,
                    scope="ip",
                )
            return LockoutState(locked=False, retry_after_seconds=0, scope="none")

    def record_failure(self, *, identifier: str, source_ip: str, when: datetime) -> None:
        identifier_key = self._normalise_identifier(identifier)
        with self._lock:
            self._identifier_hits[identifier_key].append(when)
            self._ip_hits[source_ip].append(when)

    def record_success(self, *, identifier: str) -> None:
        identifier_key = self._normalise_identifier(identifier)
        with self._lock:
            self._identifier_hits.pop(identifier_key, None)
            self._consecutive_lockouts.pop(identifier_key, None)
            self._lockout_until.pop(identifier_key, None)

    # ---- helpers ------------------------------------------------------

    @staticmethod
    def _normalise_identifier(identifier: str) -> str:
        # Emails are case-insensitive by RFC 5321; lower-casing the
        # identifier prevents `User@Example.com` from getting a fresh
        # counter just because of capitalisation. Non-email identifiers
        # are pass-through.
        return identifier.strip().lower() if "@" in identifier else identifier.strip()

    def _prune_locked(self, identifier_key: str, source_ip: str, when: datetime) -> None:
        identifier_cutoff = when - self._identifier_window
        identifier_deque = self._identifier_hits.get(identifier_key)
        if identifier_deque is not None:
            while identifier_deque and identifier_deque[0] < identifier_cutoff:
                identifier_deque.popleft()
            if not identifier_deque:
                self._identifier_hits.pop(identifier_key, None)

        ip_cutoff = when - self._ip_window
        ip_deque = self._ip_hits.get(source_ip)
        if ip_deque is not None:
            while ip_deque and ip_deque[0] < ip_cutoff:
                ip_deque.popleft()
            if not ip_deque:
                self._ip_hits.pop(source_ip, None)


__all__ = ["InMemoryLoginAttemptThrottle"]
