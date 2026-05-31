"""UserRepository outbound port.

Implementations MUST persist using the active ``UnitOfWork``'s session — no
implementation may open its own database connection. The Protocol is
``runtime_checkable`` so tests can use ``isinstance`` on fakes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.identity.domain import User


@runtime_checkable
class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def list_by_ids(self, user_ids: Iterable[UUID]) -> Sequence[User]: ...

    async def get_by_external_sub(self, external_sub: str) -> User | None: ...

    async def add(self, user: User) -> None: ...

    async def update(self, user: User) -> None: ...


__all__ = ["UserRepository"]
