"""Unit tests for the Redis login-attempt throttle adapter.

The Redis client is faked so the tests run without a redis-server.
The focus is the fail-open contract — every Redis call must absorb
:class:`redis.RedisError` and return a safe default — plus the
shape of the pipeline interactions on the happy path.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

redis_pkg = pytest.importorskip("redis")
from contexts.identity.adapters.outbound.login_attempt_throttle_redis import (  # noqa: E402
    RedisLoginAttemptThrottle,
)

UTC = UTC
BASE = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
IP = "203.0.113.4"


class FakePipeline:
    """Records pipeline calls and returns a configurable script."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def zremrangebyscore(self, *args: Any) -> FakePipeline:
        self.calls.append(("zremrangebyscore", args))
        return self

    def zcard(self, *args: Any) -> FakePipeline:
        self.calls.append(("zcard", args))
        return self

    def zrange(self, *args: Any, **kwargs: Any) -> FakePipeline:
        self.calls.append(("zrange", args))
        return self

    def zadd(self, *args: Any) -> FakePipeline:
        self.calls.append(("zadd", args))
        return self

    def expire(self, *args: Any) -> FakePipeline:
        self.calls.append(("expire", args))
        return self

    def execute(self) -> list[Any]:
        return self._script


class FakeRedis:
    def __init__(self, *, pipeline_script: list[Any] | None = None) -> None:
        self._pipeline_script = pipeline_script or [0, 0, [], 0, 0, []]
        self.deletes: list[str] = []
        self._raise: Exception | None = None

    def will_raise(self, exc: Exception) -> None:
        self._raise = exc

    def pipeline(self) -> FakePipeline:
        if self._raise is not None:
            raise self._raise
        return FakePipeline(self._pipeline_script)

    def delete(self, key: str) -> None:
        if self._raise is not None:
            raise self._raise
        self.deletes.append(key)


def test_check_unlocked_when_counts_below_threshold() -> None:
    fake = FakeRedis(pipeline_script=[0, 2, [], 0, 5, []])
    throttle = RedisLoginAttemptThrottle(client=fake)  # type: ignore[arg-type]
    state = throttle.check(identifier="ada@b.io", source_ip=IP, when=BASE)
    assert state.locked is False
    assert state.scope == "none"


def test_check_locks_on_identifier_threshold() -> None:
    fake = FakeRedis(
        pipeline_script=[
            0,
            5,
            [(b"member", BASE.timestamp() - 60.0)],
            0,
            5,
            [],
        ]
    )
    throttle = RedisLoginAttemptThrottle(
        client=fake,  # type: ignore[arg-type]
        identifier_limit=5,
        identifier_window=timedelta(seconds=120),
    )
    state = throttle.check(identifier="ada@b.io", source_ip=IP, when=BASE)
    assert state.locked is True
    assert state.scope == "identifier"
    # 120s window - 60s elapsed = 60s remaining.
    assert 55 <= state.retry_after_seconds <= 60


def test_check_fails_open_on_redis_error() -> None:
    fake = FakeRedis()
    fake.will_raise(redis_pkg.RedisError("connection refused"))
    throttle = RedisLoginAttemptThrottle(client=fake)  # type: ignore[arg-type]
    state = throttle.check(identifier="ada@b.io", source_ip=IP, when=BASE)
    assert state.locked is False
    assert state.retry_after_seconds == 0
    assert state.scope == "none"


def test_record_failure_swallows_redis_error() -> None:
    fake = FakeRedis()
    fake.will_raise(redis_pkg.RedisError("conn refused"))
    throttle = RedisLoginAttemptThrottle(client=fake)  # type: ignore[arg-type]
    throttle.record_failure(identifier="ada@b.io", source_ip=IP, when=BASE)


def test_record_success_deletes_identifier_key() -> None:
    fake = FakeRedis()
    throttle = RedisLoginAttemptThrottle(client=fake)  # type: ignore[arg-type]
    throttle.record_success(identifier="ada@b.io")
    assert fake.deletes == ["login_throttle:id:ada@b.io"]


def test_record_success_swallows_redis_error() -> None:
    fake = FakeRedis()
    fake.will_raise(redis_pkg.RedisError("conn refused"))
    throttle = RedisLoginAttemptThrottle(client=fake)  # type: ignore[arg-type]
    throttle.record_success(identifier="ada@b.io")


def test_record_failure_pipelines_both_zadds() -> None:
    fake = FakeRedis()
    pipelines: list[FakePipeline] = []
    original_pipeline = fake.pipeline

    def capture() -> FakePipeline:
        pipe = original_pipeline()
        pipelines.append(pipe)
        return pipe

    fake.pipeline = capture  # type: ignore[assignment]
    throttle = RedisLoginAttemptThrottle(client=fake)  # type: ignore[arg-type]
    throttle.record_failure(identifier="ada@b.io", source_ip=IP, when=BASE)
    assert len(pipelines) == 1
    op_names = [call[0] for call in pipelines[0].calls]
    assert op_names.count("zadd") == 2
    assert op_names.count("expire") == 2
