"""Unit tests for :class:`ListMembers`.

The use case is a thin orchestrator over ``MembershipRepository.list_page``
plus the UoW envelope. The route depends on it — a drift in signature
or pagination plumbing surfaces here, not at runtime.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.tenants.application.use_cases.list_members import (
    LIST_MEMBERS_MAX_LIMIT,
    LIST_MEMBERS_MAX_Q_LENGTH,
    ListMembers,
    ListMembersQuery,
)
from contexts.tenants.domain import Role
from tests._factories.tenants import make_membership


async def test_list_members_returns_page_for_tenant(fake_uow, membership_repo) -> None:
    tenant_id = uuid4()
    mine = make_membership(tenant_id=tenant_id)
    other = make_membership()  # different tenant_id
    membership_repo.rows = [mine, other]

    uc = ListMembers(uow=fake_uow, membership_repository=membership_repo)
    query = ListMembersQuery(tenant_id=tenant_id)
    result = await uc.execute(query)

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].user_id == mine.user_id
    assert fake_uow.begin_count == 1
    assert fake_uow.committed is True


async def test_list_members_filters_by_role(fake_uow, membership_repo) -> None:
    tenant_id = uuid4()
    admin = make_membership(tenant_id=tenant_id, role=Role.ADMIN)
    viewer = make_membership(tenant_id=tenant_id, role=Role.VIEWER)
    membership_repo.rows = [admin, viewer]

    uc = ListMembers(uow=fake_uow, membership_repository=membership_repo)
    result = await uc.execute(ListMembersQuery(tenant_id=tenant_id, roles=(Role.ADMIN,)))

    assert result.total == 1
    assert result.items[0].user_id == admin.user_id


async def test_list_members_returns_empty_page_when_no_rows(fake_uow, membership_repo) -> None:
    uc = ListMembers(uow=fake_uow, membership_repository=membership_repo)
    result = await uc.execute(ListMembersQuery(tenant_id=uuid4()))

    assert result.items == []
    assert result.total == 0
    assert fake_uow.begin_count == 1


def test_list_members_query_rejects_limit_above_cap() -> None:
    with pytest.raises(ValueError, match="limit"):
        ListMembersQuery(tenant_id=uuid4(), limit=LIST_MEMBERS_MAX_LIMIT + 1)


def test_list_members_query_rejects_limit_below_one() -> None:
    with pytest.raises(ValueError, match="limit"):
        ListMembersQuery(tenant_id=uuid4(), limit=0)


def test_list_members_query_rejects_negative_offset() -> None:
    with pytest.raises(ValueError, match="offset"):
        ListMembersQuery(tenant_id=uuid4(), offset=-1)


def test_list_members_query_rejects_oversized_q() -> None:
    with pytest.raises(ValueError, match="q must be at most"):
        ListMembersQuery(tenant_id=uuid4(), q="x" * (LIST_MEMBERS_MAX_Q_LENGTH + 1))
