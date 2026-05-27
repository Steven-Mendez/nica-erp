"""Unit tests for :class:`UpdateProfile`."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.errors import UserNotFoundError
from contexts.identity.application.use_cases.update_profile import UpdateProfile
from contexts.identity.domain.email import Email
from contexts.identity.domain.user import User
from shared_kernel.adapters.context import CurrentUser

from .conftest import FakeUow


def _fixed_now() -> datetime:
    return datetime(2026, 5, 26, 13, 0, 0, tzinfo=UTC)


async def test_update_profile_updates_user_when_found(
    fake_uow: FakeUow, current_user: CurrentUser
) -> None:
    user = User.register(
        external_sub=current_user.external_sub,
        email=Email("a@b.io"),
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC),
    )
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = user
    use_case = UpdateProfile(user_repository=repo, uow=fake_uow, now=_fixed_now)

    result = await use_case.execute(
        current_user=current_user,
        display_name="Alice",
        locale="en-US",
    )

    assert result is user
    assert user.display_name == "Alice"
    assert user.locale == "en-US"
    assert user.updated_at == _fixed_now()
    repo.update.assert_awaited_once_with(user)
    assert fake_uow.begin_count == 1
    assert fake_uow.committed is True


async def test_update_profile_raises_user_not_found(
    fake_uow: FakeUow, current_user: CurrentUser
) -> None:
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None
    use_case = UpdateProfile(user_repository=repo, uow=fake_uow, now=_fixed_now)

    with pytest.raises(UserNotFoundError):
        await use_case.execute(current_user=current_user, display_name="Alice")

    repo.update.assert_not_awaited()
    assert fake_uow.begin_count == 1
    assert fake_uow.rolled_back is True
