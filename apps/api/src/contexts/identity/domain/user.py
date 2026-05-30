"""User aggregate for the identity context.

A `User` is the canonical principal in the system: it carries the external
subject (Cognito `sub` in AWS, the local auth row's user id locally), the
canonical email, and profile preferences. Registration records a
`UserRegistered` domain event; profile edits mutate state silently (sprint 02
does not need a `ProfileUpdated` event yet).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from contexts.identity.domain.email import Email
from contexts.identity.domain.events import UserRegistered
from shared_kernel.domain.aggregate import AggregateRoot


class User(AggregateRoot[UUID]):
    """Identity-context aggregate root."""

    __slots__ = (
        "_created_at",
        "_display_name",
        "_email",
        "_external_sub",
        "_locale",
        "_preferences",
        "_timezone",
        "_updated_at",
    )

    def __init__(
        self,
        *,
        id_: UUID,
        external_sub: str,
        email: Email,
        display_name: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        preferences: dict[str, Any] | None = None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id_)
        self._external_sub = external_sub
        self._email = email
        self._display_name = display_name
        self._locale = locale
        self._timezone = timezone
        self._preferences: dict[str, Any] = dict(preferences) if preferences else {}
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def register(
        cls,
        *,
        external_sub: str,
        email: Email,
        now: datetime,
    ) -> User:
        # ``display_name``, ``locale`` and ``timezone`` start NULL; the
        # SPA's ``/welcome`` screen captures the first two on first login.
        user = cls(
            id_=UUID(external_sub),
            external_sub=external_sub,
            email=email,
            display_name=None,
            locale=None,
            timezone=None,
            created_at=now,
            updated_at=now,
        )
        user._record(
            UserRegistered(
                user_id=user.id,
                email=email.value,
                registered_at=now,
            )
        )
        return user

    def update_profile(
        self,
        *,
        display_name: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        preferences: dict[str, Any] | None = None,
        now: datetime,
    ) -> None:
        if display_name is not None:
            self._display_name = display_name
        if locale is not None:
            self._locale = locale
        if timezone is not None:
            self._timezone = timezone
        if preferences is not None:
            self._preferences = dict(preferences)
        self._updated_at = now

    # Read-only accessors ------------------------------------------------------
    @property
    def external_sub(self) -> str:
        return self._external_sub

    @property
    def email(self) -> Email:
        return self._email

    @property
    def display_name(self) -> str | None:
        return self._display_name

    @property
    def locale(self) -> str | None:
        return self._locale

    @property
    def timezone(self) -> str | None:
        return self._timezone

    @property
    def preferences(self) -> dict[str, Any]:
        return self._preferences

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at


__all__ = ["User"]
