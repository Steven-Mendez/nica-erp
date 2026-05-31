"""``ListMembers`` — paginated/filtered/sorted view of a tenant's members.

The result rows are *enriched* with the matching ``users.display_name``
and ``users.email`` via a SQL LEFT JOIN in the repository, so the HTTP
adapter no longer needs a second round-trip to the identity context to
hydrate the cells the SPA shows in the members table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from contexts.tenants.application.ports.outbound import MembershipRepository
from contexts.tenants.domain import MembershipStatus, Role
from shared_kernel.application.unit_of_work import UnitOfWork

ListMembersSortField = Literal["joined_at", "display_name", "email", "role"]
ListMembersSortDir = Literal["asc", "desc"]

# Cap matches the spec's `limit <= 100`; the value lives in the
# application layer so adapters import it instead of redefining it.
LIST_MEMBERS_MAX_LIMIT = 100
LIST_MEMBERS_DEFAULT_LIMIT = 25
LIST_MEMBERS_MAX_Q_LENGTH = 200


@dataclass(slots=True, frozen=True)
class ListMembersQuery:
    """Inputs for paginated/filtered/sorted member list.

    All filter fields are optional. ``roles`` and ``statuses`` are
    treated as "no filter" when empty / ``None``.
    """

    tenant_id: UUID
    q: str | None = None
    roles: tuple[Role, ...] = field(default_factory=tuple)
    statuses: tuple[MembershipStatus, ...] = field(default_factory=tuple)
    sort: ListMembersSortField = "joined_at"
    dir: ListMembersSortDir = "asc"
    limit: int = LIST_MEMBERS_DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if not (1 <= self.limit <= LIST_MEMBERS_MAX_LIMIT):
            raise ValueError(f"limit must be in [1, {LIST_MEMBERS_MAX_LIMIT}]; got {self.limit}")
        if self.offset < 0:
            raise ValueError(f"offset must be >= 0; got {self.offset}")
        if self.q is not None and len(self.q) > LIST_MEMBERS_MAX_Q_LENGTH:
            raise ValueError(
                f"q must be at most {LIST_MEMBERS_MAX_Q_LENGTH} characters; got {len(self.q)}"
            )


@dataclass(slots=True, frozen=True)
class MemberView:
    """A ``Membership`` row enriched with the joined user's profile."""

    id: UUID
    user_id: UUID
    tenant_id: UUID
    role: Role
    status: MembershipStatus
    joined_at: datetime
    removed_at: datetime | None
    display_name: str | None
    email: str | None


@dataclass(slots=True, frozen=True)
class ListMembersResult:
    items: list[MemberView]
    total: int


@dataclass(slots=True)
class ListMembers:
    uow: UnitOfWork
    membership_repository: MembershipRepository

    async def execute(self, query: ListMembersQuery) -> ListMembersResult:
        async with self.uow.begin():
            items, total = await self.membership_repository.list_page(query)
        return ListMembersResult(items=list(items), total=total)


__all__ = [
    "LIST_MEMBERS_DEFAULT_LIMIT",
    "LIST_MEMBERS_MAX_LIMIT",
    "LIST_MEMBERS_MAX_Q_LENGTH",
    "ListMembers",
    "ListMembersQuery",
    "ListMembersResult",
    "ListMembersSortDir",
    "ListMembersSortField",
    "MemberView",
]
