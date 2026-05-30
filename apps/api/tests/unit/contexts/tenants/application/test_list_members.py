"""Unit tests for :class:`ListMembers`.

The use case is a pass-through to the membership repository, but the
route ``GET /v1/tenants/{tenant_id}/members`` depends on it. A drift
in the signature or the UoW envelope surfaces here, not at runtime.

Worked example of ``tests/_factories/tenants`` consumption.
"""

from __future__ import annotations

from uuid import uuid4

from contexts.tenants.application.use_cases.list_members import ListMembers
from tests._factories.tenants import make_membership


async def test_list_members_returns_repository_rows_for_tenant(fake_uow, membership_repo) -> None:
    tenant_id = uuid4()
    mine = make_membership(tenant_id=tenant_id)
    other = make_membership()  # different tenant_id
    membership_repo.rows = [mine, other]

    uc = ListMembers(uow=fake_uow, membership_repository=membership_repo)
    result = await uc.execute(tenant_id=tenant_id)

    assert result == [mine]
    assert fake_uow.begin_count == 1
    assert fake_uow.committed is True


async def test_list_members_returns_empty_when_no_rows(fake_uow, membership_repo) -> None:
    uc = ListMembers(uow=fake_uow, membership_repository=membership_repo)
    result = await uc.execute(tenant_id=uuid4())

    assert result == []
    assert fake_uow.begin_count == 1
