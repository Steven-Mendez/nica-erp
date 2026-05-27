"""Unit tests for :class:`ResendCode`."""

from __future__ import annotations

from unittest.mock import AsyncMock

from contexts.identity.application.use_cases.resend_code import ResendCode


async def test_resend_code_passthrough() -> None:
    idp = AsyncMock()
    use_case = ResendCode(identity_provider=idp)

    await use_case.execute(email="a@b.io")

    idp.resend_confirmation.assert_awaited_once_with(email="a@b.io")
