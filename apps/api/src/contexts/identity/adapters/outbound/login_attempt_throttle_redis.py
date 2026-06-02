"""Redis-backed login-attempt throttle adapter.

Two Redis sorted sets per principal hold the sliding-window failure
timestamps:

  - ``login_throttle:id:<identifier>``  — keyed on the (lowercased)
    identifier the operator submitted.
  - ``login_throttle:ip:<source_ip>``   — keyed on the request's
    source IP.

On every ``check`` we prune both sets to the configured window via
``ZREMRANGEBYSCORE`` and read the resulting cardinalities with
``ZCARD``. On ``record_failure`` we ``ZADD`` the failure timestamp
(score = epoch seconds, member = epoch milliseconds so duplicates
in the same second do not collapse). On ``record_success`` we
delete the identifier's set — the IP counter is intentionally
preserved.

**Fail-open**: every Redis call is wrapped in a try/except over
:class:`redis.RedisError`. A connection loss returns
``LockoutState(locked=False, …)`` from ``check`` and silently
returns from ``record_failure`` / ``record_success`` after logging a
warning. The reasoning is documented in the spec: a Redis outage
must not lock every operator out of the SPA. The trade-off is that
a sustained Redis outage temporarily lifts the throttle entirely.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from redis import Redis, RedisError

from contexts.identity.application.login_attempt_throttle import (
    LockoutState,
    LoginAttemptThrottle,
)

logger = logging.getLogger(__name__)


class RedisLoginAttemptThrottle(LoginAttemptThrottle):
    """Sliding-window throttle backed by two Redis sorted sets per principal.

    One set tracks failures per identifier (lowercased email), a second
    tracks failures per source IP. Every ``check`` prunes both sets to
    the configured window via ``ZREMRANGEBYSCORE`` and reads the
    cardinality with ``ZCARD``; ``record_failure`` ``ZADD``s the
    failure timestamp; ``record_success`` deletes the identifier's set
    only — the IP set is preserved on purpose because a successful
    authentication does not absolve the calling IP of credential
    stuffing concerns.

    Every Redis call is wrapped in a ``try``/``except RedisError`` that
    logs and degrades gracefully: ``check`` returns
    ``LockoutState(locked=False, …)`` so a sustained Redis outage
    temporarily disables the throttle rather than locking everyone
    out, and the mutating calls swallow the error. The trade-off is
    documented in the spec and is the same fail-open posture every
    other "advisory" middleware (rate-limit, audit log) takes on the
    same code path.
    """

    _ID_KEY = "login_throttle:id:{identifier}"
    _IP_KEY = "login_throttle:ip:{source_ip}"

    def __init__(
        self,
        *,
        client: Redis,
        identifier_limit: int = 5,
        identifier_window: timedelta = timedelta(minutes=15),
        ip_limit: int = 20,
        ip_window: timedelta = timedelta(minutes=15),
    ) -> None:
        if identifier_limit < 1 or ip_limit < 1:
            raise ValueError("limits must be >= 1")
        self._client = client
        self._identifier_limit = identifier_limit
        self._identifier_window = identifier_window
        self._ip_limit = ip_limit
        self._ip_window = ip_window

    # ---- LoginAttemptThrottle Protocol --------------------------------

    def check(self, *, identifier: str, source_ip: str, when: datetime) -> LockoutState:
        identifier_key = self._identifier_key(identifier)
        ip_key = self._ip_key(source_ip)
        when_score = when.timestamp()
        identifier_cutoff = (when - self._identifier_window).timestamp()
        ip_cutoff = (when - self._ip_window).timestamp()

        try:
            pipe = self._client.pipeline()
            pipe.zremrangebyscore(identifier_key, "-inf", identifier_cutoff)
            pipe.zcard(identifier_key)
            pipe.zrange(identifier_key, 0, 0, withscores=True)
            pipe.zremrangebyscore(ip_key, "-inf", ip_cutoff)
            pipe.zcard(ip_key)
            pipe.zrange(ip_key, 0, 0, withscores=True)
            _, id_count, id_oldest, _, ip_count, ip_oldest = pipe.execute()
        except RedisError as exc:
            logger.warning("redis throttle.check failed open: %s", exc)
            return LockoutState(locked=False, retry_after_seconds=0, scope="none")

        if id_count >= self._identifier_limit:
            seconds = self._retry_after(id_oldest, self._identifier_window, when_score)
            return LockoutState(locked=True, retry_after_seconds=seconds, scope="identifier")
        if ip_count >= self._ip_limit:
            seconds = self._retry_after(ip_oldest, self._ip_window, when_score)
            return LockoutState(locked=True, retry_after_seconds=seconds, scope="ip")
        return LockoutState(locked=False, retry_after_seconds=0, scope="none")

    def record_failure(self, *, identifier: str, source_ip: str, when: datetime) -> None:
        score = when.timestamp()
        # Member uses microseconds so two failures inside the same second
        # do not collide into a single set entry.
        member = f"{int(when.timestamp() * 1_000_000)}"
        identifier_key = self._identifier_key(identifier)
        ip_key = self._ip_key(source_ip)
        try:
            pipe = self._client.pipeline()
            pipe.zadd(identifier_key, {member: score})
            pipe.expire(identifier_key, int(self._identifier_window.total_seconds()) + 60)
            pipe.zadd(ip_key, {member: score})
            pipe.expire(ip_key, int(self._ip_window.total_seconds()) + 60)
            pipe.execute()
        except RedisError as exc:
            logger.warning("redis throttle.record_failure failed open: %s", exc)

    def record_success(self, *, identifier: str) -> None:
        identifier_key = self._identifier_key(identifier)
        try:
            self._client.delete(identifier_key)
        except RedisError as exc:
            logger.warning("redis throttle.record_success failed open: %s", exc)

    # ---- helpers ------------------------------------------------------

    def _identifier_key(self, identifier: str) -> str:
        normalised = identifier.strip().lower() if "@" in identifier else identifier.strip()
        return self._ID_KEY.format(identifier=normalised)

    def _ip_key(self, source_ip: str) -> str:
        return self._IP_KEY.format(source_ip=source_ip)

    @staticmethod
    def _retry_after(
        oldest_entry: list[tuple[bytes, float]], window: timedelta, now_score: float
    ) -> int:
        if not oldest_entry:
            return 1
        _, oldest_score = oldest_entry[0]
        unlock_at = oldest_score + window.total_seconds()
        seconds = int(unlock_at - now_score)
        return max(seconds, 1)


__all__ = ["RedisLoginAttemptThrottle"]
