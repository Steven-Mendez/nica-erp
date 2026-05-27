"""Unit tests for :class:`RegisterUser`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.use_cases.register_user import RegisterUser
from contexts.identity.domain.password import PasswordPolicyError


async def test_happy_path_calls_register_once() -> None:
    idp = AsyncMock()
    idp.register.return_value = "sub-1"
    use_case = RegisterUser(identity_provider=idp)

    await use_case.execute(email="a@b.io", password="StrongPass123!")

    idp.register.assert_awaited_once_with(email="a@b.io", password="StrongPass123!")


async def test_weak_password_raises_and_does_not_call_register() -> None:
    idp = AsyncMock()
    use_case = RegisterUser(identity_provider=idp)

    with pytest.raises(PasswordPolicyError):
        await use_case.execute(email="a@b.io", password="weak")

    idp.register.assert_not_awaited()


async def test_malformed_email_raises_and_does_not_call_register() -> None:
    idp = AsyncMock()
    use_case = RegisterUser(identity_provider=idp)

    with pytest.raises(ValueError):
        await use_case.execute(email="not-an-email", password="StrongPass123!")

    idp.register.assert_not_awaited()
