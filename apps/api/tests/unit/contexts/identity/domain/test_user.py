"""Unit tests for the User aggregate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from contexts.identity.domain.email import Email
from contexts.identity.domain.events import UserRegistered
from contexts.identity.domain.user import User


def test_register_records_single_user_registered_event() -> None:
    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    user = User.register(
        external_sub="22222222-2222-2222-2222-222222222222", email=Email("a@b.io"), now=t
    )

    events = user.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, UserRegistered)
    assert event.user_id == user.id
    assert event.email == "a@b.io"
    assert event.registered_at == t


def test_register_leaves_profile_fields_null_for_welcome_screen() -> None:
    """A freshly registered user has NULL display_name/locale/timezone.

    The SPA's ``/welcome`` route captures display_name + timezone on
    first login (locale is deferred per ADR-0033). Sprint 3.6 removed
    the Nicaragua-centric defaults the column previously held.
    """

    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    user = User.register(
        external_sub="22222222-2222-2222-2222-222222222222", email=Email("a@b.io"), now=t
    )
    assert user.locale is None
    assert user.timezone is None
    assert user.display_name is None
    assert user.preferences == {}
    assert user.external_sub == "22222222-2222-2222-2222-222222222222"
    assert user.created_at == t
    assert user.updated_at == t


def test_update_profile_updates_field_and_updated_at() -> None:
    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    user = User.register(
        external_sub="22222222-2222-2222-2222-222222222222", email=Email("a@b.io"), now=t
    )
    user.pull_events()  # clear

    t2 = t + timedelta(hours=1)
    user.update_profile(display_name="Alice", now=t2)

    assert user.display_name == "Alice"
    assert user.updated_at == t2
    # No event for profile updates in sprint 02.
    assert user.pull_events() == []


def test_update_profile_only_applies_non_none_updates() -> None:
    t = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
    user = User.register(
        external_sub="22222222-2222-2222-2222-222222222222", email=Email("a@b.io"), now=t
    )
    user.update_profile(display_name="Alice", now=t)

    t2 = t + timedelta(hours=1)
    user.update_profile(locale="en-US", now=t2)

    assert user.display_name == "Alice"  # unchanged
    assert user.locale == "en-US"
    assert user.updated_at == t2
