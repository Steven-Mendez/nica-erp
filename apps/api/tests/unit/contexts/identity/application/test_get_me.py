"""Unit tests for :class:`GetMe`."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.errors import UserNotFoundError
from contexts.identity.application.use_cases.get_me import GetMe
from contexts.identity.domain.email import Email
from contexts.identity.domain.user import User
from shared_kernel.adapters.context import CurrentUser

from .conftest import FakeUow


async def test_get_me_returns_user_when_repo_finds_it(
    fake_uow: FakeUow, current_user: CurrentUser
) -> None:
    user = User.register(
        external_sub=current_user.external_sub,
        email=Email("a@b.io"),
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC),
    )
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = user
    use_case = GetMe(user_repository=repo, uow=fake_uow)

    result = await use_case.execute(current_user=current_user)

    assert result is user
    repo.get_by_external_sub.assert_awaited_once_with(current_user.external_sub)
    assert fake_uow.begin_count == 1
    assert fake_uow.committed is True


async def test_get_me_raises_user_not_found_when_repo_returns_none(
    fake_uow: FakeUow, current_user: CurrentUser
) -> None:
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None
    use_case = GetMe(user_repository=repo, uow=fake_uow)

    with pytest.raises(UserNotFoundError):
        await use_case.execute(current_user=current_user)

    assert fake_uow.begin_count == 1
    assert fake_uow.rolled_back is True
