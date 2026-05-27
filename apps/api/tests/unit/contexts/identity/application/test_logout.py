"""Unit tests for :class:`Logout`."""

from __future__ import annotations

from unittest.mock import AsyncMock

from contexts.identity.application.use_cases.logout import Logout
from shared_kernel.adapters.context import CurrentUser


async def test_logout_calls_global_signout_once(current_user: CurrentUser) -> None:
    idp = AsyncMock()
    use_case = Logout(identity_provider=idp)

    await use_case.execute(current_user=current_user)

    idp.global_signout.assert_awaited_once_with(external_sub=current_user.external_sub)


async def test_logout_is_idempotent(current_user: CurrentUser) -> None:
    idp = AsyncMock()
    use_case = Logout(identity_provider=idp)

    first = await use_case.execute(current_user=current_user)
    second = await use_case.execute(current_user=current_user)

    assert first is None
    assert second is None
    assert idp.global_signout.await_count == 2
