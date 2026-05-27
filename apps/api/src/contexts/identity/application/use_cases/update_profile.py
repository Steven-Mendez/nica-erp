"""``UpdateProfile`` use case — mutate the calling user's profile fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from contexts.identity.application.errors import UserNotFoundError
from contexts.identity.application.ports.outbound import UserRepository
from contexts.identity.domain import User
from shared_kernel.adapters.context import CurrentUser
from shared_kernel.application.unit_of_work import UnitOfWork


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateProfile:
    user_repository: UserRepository
    uow: UnitOfWork
    now: Callable[[], datetime] = field(default=_utc_now)

    async def execute(
        self,
        *,
        current_user: CurrentUser,
        display_name: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        preferences: dict[str, Any] | None = None,
    ) -> User:
        async with self.uow.begin():
            user = await self.user_repository.get_by_external_sub(current_user.external_sub)
            if user is None:
                raise UserNotFoundError(current_user.external_sub)
            user.update_profile(
                display_name=display_name,
                locale=locale,
                timezone=timezone,
                preferences=preferences,
                now=self.now(),
            )
            await self.user_repository.update(user)
            return user


__all__ = ["UpdateProfile"]
