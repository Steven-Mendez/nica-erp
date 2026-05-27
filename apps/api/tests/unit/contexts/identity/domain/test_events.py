"""Unit tests for identity domain events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from contexts.identity.domain.events import (
    IDENTITY_PASSWORD_RESET_EVENT_TYPE,
    IDENTITY_USER_REGISTERED_EVENT_TYPE,
    PasswordReset,
    UserRegistered,
)


def test_user_registered_event_id_and_occurred_at_defaults() -> None:
    u = uuid4()
    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    event = UserRegistered(user_id=u, email="a@b.io", registered_at=t)

    assert event.event_id is not None
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset() == UTC.utcoffset(None)
    assert event.user_id == u
    assert event.email == "a@b.io"
    assert event.registered_at == t


def test_user_registered_is_frozen() -> None:
    u = uuid4()
    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    event = UserRegistered(user_id=u, email="a@b.io", registered_at=t)

    with pytest.raises((AttributeError, TypeError)):
        event.email = "other@example.com"  # type: ignore[misc]


def test_password_reset_event_defaults() -> None:
    u = uuid4()
    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    event = PasswordReset(user_id=u, reset_at=t)

    assert event.event_id is not None
    assert event.occurred_at.tzinfo is not None
    assert event.user_id == u
    assert event.reset_at == t


def test_event_type_constants_are_stable() -> None:
    assert IDENTITY_USER_REGISTERED_EVENT_TYPE == "identity.UserRegistered"
    assert IDENTITY_PASSWORD_RESET_EVENT_TYPE == "identity.PasswordReset"
