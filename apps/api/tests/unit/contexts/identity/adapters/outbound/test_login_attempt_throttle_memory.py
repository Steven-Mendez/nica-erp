"""Unit tests for the in-memory login-attempt throttle adapter.

The sliding window and the two-counter contract are tightly coupled
to the application-level lockout semantics, so these tests own the
authoritative coverage of the threshold + window-slide + success
behaviours. The Redis adapter shares the same protocol but is
tested separately against a faked client.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from contexts.identity.adapters.outbound.login_attempt_throttle_memory import (
    InMemoryLoginAttemptThrottle,
)

UTC = UTC
BASE = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
IP_A = "203.0.113.4"
IP_B = "203.0.113.99"


def test_unlocked_when_no_history() -> None:
    throttle = InMemoryLoginAttemptThrottle()
    state = throttle.check(identifier="ada@b.io", source_ip=IP_A, when=BASE)
    assert state.locked is False
    assert state.retry_after_seconds == 0
    assert state.scope == "none"


def test_identifier_locks_after_five_failures() -> None:
    throttle = InMemoryLoginAttemptThrottle()
    for i in range(5):
        throttle.record_failure(
            identifier="ada@b.io",
            source_ip=IP_A,
            when=BASE + timedelta(seconds=i),
        )
    state = throttle.check(identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=5))
    assert state.locked is True
    assert state.scope == "identifier"
    assert state.retry_after_seconds >= 1


def test_identifier_lock_clears_when_window_slides() -> None:
    throttle = InMemoryLoginAttemptThrottle(identifier_window=timedelta(seconds=60))
    for i in range(5):
        throttle.record_failure(
            identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=i)
        )
    locked = throttle.check(identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=5))
    assert locked.locked is True

    # Move "now" 61s forward — all 5 failures fall outside the window.
    later = throttle.check(identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=66))
    assert later.locked is False


def test_record_success_resets_identifier_but_not_ip() -> None:
    throttle = InMemoryLoginAttemptThrottle(ip_limit=4)
    for i in range(4):
        throttle.record_failure(
            identifier="ada@b.io",
            source_ip=IP_A,
            when=BASE + timedelta(seconds=i),
        )
    throttle.record_success(identifier="ada@b.io")

    # Identifier counter cleared → not locked by identifier.
    same_id = throttle.check(
        identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=4)
    )
    # But IP threshold was 4 → IP-scope lock survives the success.
    assert same_id.locked is True
    assert same_id.scope == "ip"


def test_ip_locks_independently_of_identifier() -> None:
    throttle = InMemoryLoginAttemptThrottle(ip_limit=3)
    # Three failures from the same IP against three different identifiers.
    throttle.record_failure(identifier="a@x.io", source_ip=IP_A, when=BASE)
    throttle.record_failure(identifier="b@x.io", source_ip=IP_A, when=BASE + timedelta(seconds=1))
    throttle.record_failure(identifier="c@x.io", source_ip=IP_A, when=BASE + timedelta(seconds=2))
    state = throttle.check(identifier="d@x.io", source_ip=IP_A, when=BASE + timedelta(seconds=3))
    assert state.locked is True
    assert state.scope == "ip"


def test_ip_counter_does_not_pollute_other_ip() -> None:
    throttle = InMemoryLoginAttemptThrottle(ip_limit=3)
    for i in range(3):
        throttle.record_failure(
            identifier="a@x.io", source_ip=IP_A, when=BASE + timedelta(seconds=i)
        )
    other = throttle.check(identifier="a@x.io", source_ip=IP_B, when=BASE + timedelta(seconds=3))
    # IP_B is fresh — IP_A's lockout does not bleed across IPs.
    assert other.locked is False


def test_identifier_email_normalisation() -> None:
    throttle = InMemoryLoginAttemptThrottle()
    for i in range(5):
        throttle.record_failure(
            identifier="Ada@B.IO",
            source_ip=IP_A,
            when=BASE + timedelta(seconds=i),
        )
    # Lowercase + uppercase forms hit the same bucket.
    state = throttle.check(identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=5))
    assert state.locked is True
    assert state.scope == "identifier"


def test_retry_after_reflects_window_slide() -> None:
    throttle = InMemoryLoginAttemptThrottle(identifier_window=timedelta(minutes=15))
    # 5 failures at BASE; check 30s later → ~14 minutes and change remain.
    for _ in range(5):
        throttle.record_failure(identifier="ada@b.io", source_ip=IP_A, when=BASE)
    state = throttle.check(identifier="ada@b.io", source_ip=IP_A, when=BASE + timedelta(seconds=30))
    assert state.locked is True
    # 15 minutes - 30 seconds = 14 minutes 30 seconds = 870 seconds.
    assert 860 <= state.retry_after_seconds <= 870
