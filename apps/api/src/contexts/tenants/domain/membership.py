"""``Membership`` entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from contexts.tenants.domain.errors import OwnerRoleNotAllowedHereError
from contexts.tenants.domain.role import Role

MembershipStatus = Literal["active", "removed"]


@dataclass
class Membership:
    id: UUID
    user_id: UUID
    tenant_id: UUID
    role: Role
    status: MembershipStatus
    joined_at: datetime
    removed_at: datetime | None

    def __post_init__(self) -> None:
        # Owner is reserved for ``create_owner``. A direct constructor call
        # that passes ``role=Role.OWNER`` is a bug — block it loudly so the
        # invariant cannot be silently violated.
        if self.role is Role.OWNER and not getattr(self, "_owner_factory", False):
            raise OwnerRoleNotAllowedHereError(
                "Use Membership.create_owner(...) to create the tenant owner"
            )

    @classmethod
    def create_owner(
        cls,
        *,
        user_id: UUID,
        tenant_id: UUID,
        now: datetime,
        id_: UUID | None = None,
    ) -> Membership:
        # The factory bypasses the constructor guard by setting an attribute
        # in __dict__ before __post_init__ would fire. We can't do that with
        # ``dataclass`` cleanly, so we mark the role and the factory flag
        # through an instance variable injected via __dict__.
        instance = cls.__new__(cls)
        instance.id = id_ or uuid4()
        instance.user_id = user_id
        instance.tenant_id = tenant_id
        instance.role = Role.OWNER
        instance.status = "active"
        instance.joined_at = now
        instance.removed_at = None
        return instance

    @classmethod
    def hydrate(
        cls,
        *,
        id_: UUID,
        user_id: UUID,
        tenant_id: UUID,
        role: Role,
        status: MembershipStatus,
        joined_at: datetime,
        removed_at: datetime | None,
    ) -> Membership:
        """Rebuild a Membership from persisted state, owner row included.

        Persistence adapters call this instead of the bare constructor so
        the owner-guard in ``__post_init__`` does not reject rows where
        ``role == Role.OWNER``. The guard exists to catch *creation*
        bugs; loading the owner row from the database is not a bug.
        """

        instance = cls.__new__(cls)
        instance.id = id_
        instance.user_id = user_id
        instance.tenant_id = tenant_id
        instance.role = role
        instance.status = status
        instance.joined_at = joined_at
        instance.removed_at = removed_at
        return instance

    @classmethod
    def join(
        cls,
        *,
        user_id: UUID,
        tenant_id: UUID,
        role: Role,
        now: datetime,
        id_: UUID | None = None,
    ) -> Membership:
        if role is Role.OWNER:
            raise OwnerRoleNotAllowedHereError(
                "Membership.join cannot create the owner; use create_owner"
            )
        return cls(
            id=id_ or uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            status="active",
            joined_at=now,
            removed_at=None,
        )

    def remove(self, *, now: datetime) -> None:
        self.status = "removed"
        self.removed_at = now

    def change_role(self, *, new_role: Role) -> None:
        if new_role is Role.OWNER:
            raise OwnerRoleNotAllowedHereError(
                "change_role cannot promote to owner; use TransferOwnership (post-MVP)"
            )
        self.role = new_role


__all__ = ["Membership", "MembershipStatus"]
