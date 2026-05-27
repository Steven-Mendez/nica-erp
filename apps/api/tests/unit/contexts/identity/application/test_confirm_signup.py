"""Unit tests for :class:`ConfirmSignup`."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.constants import SYSTEM_GLOBAL_TENANT_ID
from contexts.identity.application.use_cases.confirm_signup import ConfirmSignup
from contexts.identity.domain.events import (
    IDENTITY_USER_REGISTERED_EVENT_TYPE,
    IDENTITY_USER_REGISTERED_EVENT_VERSION,
)
from contexts.identity.domain.user import User

from .conftest import FakeUow


def _fixed_now() -> datetime:
    return datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)


async def test_confirm_signup_persists_user_and_emits_outbox_event(
    fake_uow: FakeUow,
) -> None:
    idp = AsyncMock()
    idp.confirm_signup.return_value = "sub-1"
    repo = AsyncMock()
    outbox = AsyncMock()

    use_case = ConfirmSignup(
        identity_provider=idp,
        user_repository=repo,
        outbox_writer=outbox,
        uow=fake_uow,
        now=_fixed_now,
    )

    await use_case.execute(email="a@b.io", code="123456")

    idp.confirm_signup.assert_awaited_once_with(email="a@b.io", code="123456")

    repo.add.assert_awaited_once()
    added_user = repo.add.await_args.kwargs.get("user") or repo.add.await_args.args[0]
    assert isinstance(added_user, User)
    assert added_user.external_sub == "sub-1"
    assert added_user.email.value == "a@b.io"

    outbox.append.assert_awaited_once()
    call_kwargs = outbox.append.await_args.kwargs
    assert call_kwargs["event_type"] == IDENTITY_USER_REGISTERED_EVENT_TYPE
    assert call_kwargs["event_version"] == IDENTITY_USER_REGISTERED_EVENT_VERSION
    assert call_kwargs["aggregate_type"] == "User"
    assert call_kwargs["aggregate_id"] == added_user.id
    assert call_kwargs["tenant_id"] == SYSTEM_GLOBAL_TENANT_ID
    payload = call_kwargs["payload"]
    assert set(payload.keys()) == {"user_id", "email", "registered_at"}
    assert payload["user_id"] == str(added_user.id)
    assert payload["email"] == "a@b.io"
    assert payload["registered_at"] == _fixed_now().isoformat()

    assert fake_uow.begin_count == 1
    assert fake_uow.committed is True
    assert fake_uow.rolled_back is False


async def test_confirm_signup_outbox_failure_rolls_back(fake_uow: FakeUow) -> None:
    idp = AsyncMock()
    idp.confirm_signup.return_value = "sub-1"
    repo = AsyncMock()
    outbox = AsyncMock()
    outbox.append.side_effect = RuntimeError("kaboom")

    use_case = ConfirmSignup(
        identity_provider=idp,
        user_repository=repo,
        outbox_writer=outbox,
        uow=fake_uow,
        now=_fixed_now,
    )

    with pytest.raises(RuntimeError):
        await use_case.execute(email="a@b.io", code="123456")

    assert fake_uow.begin_count == 1
    assert fake_uow.rolled_back is True
    assert fake_uow.committed is False
