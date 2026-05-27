"""Unit tests for :class:`ChangePassword`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.use_cases.change_password import ChangePassword
from contexts.identity.domain.password import PasswordPolicyError


async def test_weak_new_password_raises_before_port_call() -> None:
    idp = AsyncMock()
    use_case = ChangePassword(identity_provider=idp)

    with pytest.raises(PasswordPolicyError):
        await use_case.execute(
            access_token="at",
            old_password="OldStrongPass1!",
            new_password="weak",
        )

    idp.change_password.assert_not_awaited()


async def test_happy_path_calls_change_password() -> None:
    idp = AsyncMock()
    use_case = ChangePassword(identity_provider=idp)

    await use_case.execute(
        access_token="at",
        old_password="OldStrongPass1!",
        new_password="NewStrongPass1!",
    )

    idp.change_password.assert_awaited_once_with(
        access_token="at",
        old_password="OldStrongPass1!",
        new_password="NewStrongPass1!",
    )
