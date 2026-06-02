"""In-memory login-attempt throttle adapter.

Used by the local-dev and unit/integration test profiles where a Redis
server would be heavy-weight. Stores failure timestamps in two
``deque``s — one per identifier, one per source IP — and prunes them
to the configured sliding window on every call. Thread-safe via a
single coarse lock; the throughput cost is acceptable at the volumes
this adapter sees (test suites, single-process dev server).
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

from contexts.identity.application.login_attempt_throttle import (
    LockoutState,
    LoginAttemptThrottle,
)


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
        ip_window: timedelta = timedelta(minutes=15),
    ) -> None:
        if identifier_limit < 1 or ip_limit < 1:
            raise ValueError("limits must be >= 1")
        self._identifier_limit = identifier_limit
        self._identifier_window = identifier_window
        self._ip_limit = ip_limit
        self._ip_window = ip_window
        self._identifier_hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._ip_hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    # ---- LoginAttemptThrottle Protocol --------------------------------

    def check(self, *, identifier: str, source_ip: str, when: datetime) -> LockoutState:
        identifier_key = self._normalise_identifier(identifier)
        with self._lock:
            self._prune_locked(identifier_key, source_ip, when)
            identifier_count = len(self._identifier_hits.get(identifier_key, ()))
            ip_count = len(self._ip_hits.get(source_ip, ()))
            # Identifier wins ties — it's the more specific signal.
            if identifier_count >= self._identifier_limit:
                seconds = self._retry_after_locked(
                    self._identifier_hits[identifier_key], self._identifier_window, when
                )
                return LockoutState(locked=True, retry_after_seconds=seconds, scope="identifier")
            if ip_count >= self._ip_limit:
                seconds = self._retry_after_locked(self._ip_hits[source_ip], self._ip_window, when)
                return LockoutState(locked=True, retry_after_seconds=seconds, scope="ip")
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

    @staticmethod
    def _retry_after_locked(hits: deque[datetime], window: timedelta, when: datetime) -> int:
        # Earliest hit + window = moment the count will drop below the
        # threshold (sliding window). Clamp to >= 1 since the spec
        # demands a meaningful Retry-After.
        if not hits:
            return 1
        unlock_at = hits[0] + window
        seconds = int((unlock_at - when).total_seconds())
        return max(seconds, 1)


__all__ = ["InMemoryLoginAttemptThrottle"]
