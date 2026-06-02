"""Unit tests for :class:`Authenticate`."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from contexts.identity.adapters.outbound.login_attempt_throttle_memory import (
    InMemoryLoginAttemptThrottle,
)
from contexts.identity.application.errors import (
    AuthLockoutActiveError,
    InvalidCredentialsError,
    LockoutActiveError,
)
from contexts.identity.application.login_attempt_throttle import (
    LockoutState,
    LoginAttemptThrottle,
)
from contexts.identity.application.ports.outbound import Identity
from contexts.identity.application.use_cases.authenticate import Authenticate

SOURCE_IP = "203.0.113.4"


def _make_throttle() -> InMemoryLoginAttemptThrottle:
    return InMemoryLoginAttemptThrottle()


async def test_authenticate_happy_returns_identity() -> None:
    idp = AsyncMock()
    expected = Identity(
        sub="11111111-1111-1111-1111-111111111111",
        email="a@b.io",
        access_token="at",
        refresh_token="rt",
        id_token="it",
        claims={"role": "operator"},
    )
    idp.authenticate.return_value = expected
    use_case = Authenticate(identity_provider=idp, throttle=_make_throttle(), source_ip=SOURCE_IP)

    result = await use_case.execute(email="a@b.io", password="StrongPass123!")

    assert result is expected
    idp.authenticate.assert_awaited_once_with(email="a@b.io", password="StrongPass123!")


async def test_authenticate_lockout_error_propagates_with_retry_after() -> None:
    idp = AsyncMock()
    idp.authenticate.side_effect = LockoutActiveError(retry_after_seconds=42)
    use_case = Authenticate(identity_provider=idp, throttle=_make_throttle(), source_ip=SOURCE_IP)

    with pytest.raises(LockoutActiveError) as excinfo:
        await use_case.execute(email="a@b.io", password="StrongPass123!")

    assert excinfo.value.retry_after_seconds == 42


async def test_authenticate_short_circuits_when_throttle_reports_locked() -> None:
    """Throttle lockout short-circuits before any password compare."""

    idp = AsyncMock()
    fake_throttle = AsyncMock(spec=LoginAttemptThrottle)
    fake_throttle.check.return_value = LockoutState(
        locked=True, retry_after_seconds=120, scope="identifier"
    )
    use_case = Authenticate(identity_provider=idp, throttle=fake_throttle, source_ip=SOURCE_IP)

    with pytest.raises(AuthLockoutActiveError) as excinfo:
        await use_case.execute(email="a@b.io", password="StrongPass123!")

    assert excinfo.value.retry_after_seconds == 120
    assert excinfo.value.scope == "identifier"
    idp.authenticate.assert_not_awaited()


async def test_authenticate_records_failure_on_invalid_credentials() -> None:
    """A wrong password increments the throttle counter then re-raises."""

    idp = AsyncMock()
    idp.authenticate.side_effect = InvalidCredentialsError("bad creds")
    throttle = _make_throttle()
    use_case = Authenticate(identity_provider=idp, throttle=throttle, source_ip=SOURCE_IP)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="a@b.io", password="wrong")

    # 4 more failures would cross the identifier threshold.
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email="a@b.io", password="wrong")

    # The next call must lock out — the throttle saw 5 failures total.
    with pytest.raises(AuthLockoutActiveError) as excinfo:
        await use_case.execute(email="a@b.io", password="wrong")
    assert excinfo.value.scope == "identifier"


async def test_authenticate_records_success_resets_identifier_counter() -> None:
    """A clean authentication clears the identifier's failure counter."""

    idp = AsyncMock()
    throttle = _make_throttle()
    use_case = Authenticate(identity_provider=idp, throttle=throttle, source_ip=SOURCE_IP)

    # Accumulate 4 failures (1 below threshold).
    idp.authenticate.side_effect = InvalidCredentialsError("bad")
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email="a@b.io", password="wrong")

    # Successful authentication should reset the identifier counter.
    idp.authenticate.side_effect = None
    idp.authenticate.return_value = Identity(
        sub="11111111-1111-1111-1111-111111111111",
        email="a@b.io",
        access_token="at",
        refresh_token="rt",
        id_token="it",
        claims={},
    )
    await use_case.execute(email="a@b.io", password="StrongPass123!")

    # Five fresh failures from this point must NOT immediately lock —
    # the success reset the counter, so we have room for 5 more.
    idp.authenticate.side_effect = InvalidCredentialsError("bad")
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email="a@b.io", password="wrong")
    # 5th failure crosses the threshold (≥ 5 failures in window).
    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="a@b.io", password="wrong")
    with pytest.raises(AuthLockoutActiveError):
        await use_case.execute(email="a@b.io", password="wrong")


# Silence an unused-import warning when timedelta lands as a future
# helper for clock injection.
_ = timedelta
