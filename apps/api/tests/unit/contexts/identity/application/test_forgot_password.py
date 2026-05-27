"""Unit tests for :class:`ForgotPassword`."""

from __future__ import annotations

from unittest.mock import AsyncMock

from contexts.identity.application.use_cases.forgot_password import ForgotPassword


async def test_forgot_password_passthrough() -> None:
    idp = AsyncMock()
    use_case = ForgotPassword(identity_provider=idp)

    await use_case.execute(email="a@b.io")

    idp.forgot_password.assert_awaited_once_with(email="a@b.io")
