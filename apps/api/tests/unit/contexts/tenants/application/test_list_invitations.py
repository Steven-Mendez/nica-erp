"""Unit tests for :class:`ListInvitations`.

Like ``ListMembers``, this is a pass-through to a repository, but
``GET /v1/tenants/{tenant_id}/invitations`` depends on it. A drift
in the signature surfaces here, not at runtime.

Worked example of ``tests/_factories/tenants`` consumption.
"""

from __future__ import annotations

from uuid import uuid4

from contexts.tenants.application.use_cases.list_invitations import ListInvitations
from tests._factories.tenants import make_invitation


async def test_list_invitations_returns_repository_rows_for_tenant(
    fake_uow, invitation_repo
) -> None:
    tenant_id = uuid4()
    mine = make_invitation(tenant_id=tenant_id, email="alice@acme.example")
    other = make_invitation(email="bob@other.example")
    await invitation_repo.add(mine)
    await invitation_repo.add(other)

    uc = ListInvitations(uow=fake_uow, invitation_repository=invitation_repo)
    result = await uc.execute(tenant_id=tenant_id)

    assert result == [mine]
    assert fake_uow.begin_count == 1
    assert fake_uow.committed is True


async def test_list_invitations_returns_empty_when_no_rows(fake_uow, invitation_repo) -> None:
    uc = ListInvitations(uow=fake_uow, invitation_repository=invitation_repo)
    result = await uc.execute(tenant_id=uuid4())

    assert result == []
    assert fake_uow.begin_count == 1
