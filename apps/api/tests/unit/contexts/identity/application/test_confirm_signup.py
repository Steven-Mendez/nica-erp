"""Unit tests for :class:`ConfirmSignup`."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from contexts.identity.application.constants import SYSTEM_GLOBAL_TENANT_ID
from contexts.identity.application.ports.outbound import Identity
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
    idp.confirm_signup.return_value = "11111111-1111-1111-1111-111111111111"
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None
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
    assert added_user.external_sub == "11111111-1111-1111-1111-111111111111"
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
    idp.confirm_signup.return_value = "11111111-1111-1111-1111-111111111111"
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None
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


async def test_execute_without_password_returns_none(fake_uow: FakeUow) -> None:
    idp = AsyncMock()
    idp.confirm_signup.return_value = "11111111-1111-1111-1111-111111111111"
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None

    use_case = ConfirmSignup(
        identity_provider=idp,
        user_repository=repo,
        outbox_writer=AsyncMock(),
        uow=fake_uow,
        now=_fixed_now,
    )

    result = await use_case.execute(email="a@b.io", code="123456")

    assert result is None
    idp.authenticate.assert_not_awaited()


async def test_execute_with_password_returns_identity_bundle(fake_uow: FakeUow) -> None:
    idp = AsyncMock()
    idp.confirm_signup.return_value = "11111111-1111-1111-1111-111111111111"
    bundle = Identity(
        sub="11111111-1111-1111-1111-111111111111",
        email="a@b.io",
        access_token="access",
        refresh_token="refresh",
        id_token="id",
    )
    idp.authenticate.return_value = bundle
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None

    use_case = ConfirmSignup(
        identity_provider=idp,
        user_repository=repo,
        outbox_writer=AsyncMock(),
        uow=fake_uow,
        now=_fixed_now,
    )

    result = await use_case.execute(email="a@b.io", code="123456", password="Demo12345!@ab")

    assert result is bundle
    idp.confirm_signup.assert_awaited_once_with(email="a@b.io", code="123456")
    idp.authenticate.assert_awaited_once_with(email="a@b.io", password="Demo12345!@ab")
    assert fake_uow.committed is True


async def test_confirm_signup_is_idempotent_when_user_already_exists(
    fake_uow: FakeUow,
) -> None:
    """Audit F-002: a retry after a successful confirm-signup must NOT
    raise ``IntegrityError`` and must NOT emit a duplicate outbox row.
    """
    external_sub = "11111111-1111-1111-1111-111111111111"
    idp = AsyncMock()
    idp.confirm_signup.return_value = external_sub

    from contexts.identity.domain import Email

    existing = User.register(
        external_sub=external_sub,
        email=Email.parse("a@b.io"),
        now=_fixed_now(),
    )
    existing.pull_events()  # discard the event the seed aggregate "would" have emitted

    repo = AsyncMock()
    repo.get_by_external_sub.return_value = existing
    outbox = AsyncMock()

    use_case = ConfirmSignup(
        identity_provider=idp,
        user_repository=repo,
        outbox_writer=outbox,
        uow=fake_uow,
        now=_fixed_now,
    )

    await use_case.execute(email="a@b.io", code="123456")

    repo.add.assert_not_awaited()
    outbox.append.assert_not_awaited()
    assert fake_uow.committed is True


async def test_confirm_signup_swallows_race_integrity_error(
    fake_uow: FakeUow,
) -> None:
    """A concurrent insert between the pre-flight read and add() should
    be treated as idempotent, not bubble up as 500."""
    from sqlalchemy.exc import IntegrityError

    idp = AsyncMock()
    idp.confirm_signup.return_value = "11111111-1111-1111-1111-111111111111"
    repo = AsyncMock()
    repo.get_by_external_sub.return_value = None
    repo.add.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))
    outbox = AsyncMock()

    use_case = ConfirmSignup(
        identity_provider=idp,
        user_repository=repo,
        outbox_writer=outbox,
        uow=fake_uow,
        now=_fixed_now,
    )

    await use_case.execute(email="a@b.io", code="123456")

    repo.add.assert_awaited_once()
    outbox.append.assert_not_awaited()
