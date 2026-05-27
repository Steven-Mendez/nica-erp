"""Unit tests for :class:`ResetPassword`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.use_cases.reset_password import ResetPassword
from contexts.identity.domain.password import PasswordPolicyError


async def test_weak_new_password_raises_before_port_call() -> None:
    idp = AsyncMock()
    use_case = ResetPassword(identity_provider=idp)

    with pytest.raises(PasswordPolicyError):
        await use_case.execute(email="a@b.io", code="123456", new_password="weak")

    idp.confirm_forgot_password.assert_not_awaited()


async def test_happy_path_calls_confirm_forgot_password() -> None:
    idp = AsyncMock()
    use_case = ResetPassword(identity_provider=idp)

    await use_case.execute(email="a@b.io", code="123456", new_password="NewStrongPass1!")

    idp.confirm_forgot_password.assert_awaited_once_with(
        email="a@b.io", code="123456", new_password="NewStrongPass1!"
    )
