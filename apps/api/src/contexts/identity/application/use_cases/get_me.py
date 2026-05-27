"""``GetMe`` use case — load the calling user's ``User`` aggregate."""

from __future__ import annotations

from dataclasses import dataclass

from contexts.identity.application.errors import UserNotFoundError
from contexts.identity.application.ports.outbound import UserRepository
from contexts.identity.domain import User
from shared_kernel.adapters.context import CurrentUser
from shared_kernel.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True, kw_only=True)
class GetMe:
    user_repository: UserRepository
    uow: UnitOfWork

    async def execute(self, *, current_user: CurrentUser) -> User:
        async with self.uow.begin():
            user = await self.user_repository.get_by_external_sub(current_user.external_sub)
            if user is None:
                raise UserNotFoundError(current_user.external_sub)
            return user


__all__ = ["GetMe"]
