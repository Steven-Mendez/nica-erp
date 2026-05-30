"""Unit tests for :class:`Authenticate`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.errors import LockoutActiveError
from contexts.identity.application.ports.outbound import Identity
from contexts.identity.application.use_cases.authenticate import Authenticate


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
    use_case = Authenticate(identity_provider=idp)

    result = await use_case.execute(email="a@b.io", password="StrongPass123!")

    assert result is expected
    idp.authenticate.assert_awaited_once_with(email="a@b.io", password="StrongPass123!")


async def test_authenticate_lockout_error_propagates_with_retry_after() -> None:
    idp = AsyncMock()
    idp.authenticate.side_effect = LockoutActiveError(retry_after_seconds=42)
    use_case = Authenticate(identity_provider=idp)

    with pytest.raises(LockoutActiveError) as excinfo:
        await use_case.execute(email="a@b.io", password="StrongPass123!")

    assert excinfo.value.retry_after_seconds == 42
