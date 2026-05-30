"""Unit tests for :class:`RefreshToken`."""

from __future__ import annotations

from unittest.mock import AsyncMock

from contexts.identity.application.ports.outbound import Identity
from contexts.identity.application.use_cases.refresh_token import RefreshToken


async def test_refresh_token_passthrough() -> None:
    idp = AsyncMock()
    expected = Identity(
        sub="11111111-1111-1111-1111-111111111111",
        email="a@b.io",
        access_token="at2",
        refresh_token="rt2",
        id_token="it2",
    )
    idp.refresh.return_value = expected
    use_case = RefreshToken(identity_provider=idp)

    result = await use_case.execute(refresh_token="rt")

    assert result is expected
    idp.refresh.assert_awaited_once_with(refresh_token="rt")
