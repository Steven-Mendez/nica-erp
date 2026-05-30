"""Unit tests for Tenant / Membership / Invitation aggregates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from contexts.tenants.domain import (
    AuthorizationDgi,
    InvitationAlreadyAcceptedError,
    InvitationCancelledError,
    InvitationExpiredError,
    Membership,
    Municipality,
    OwnerRoleNotAllowedHereError,
    Regime,
    Role,
    Ruc,
    Tenant,
    TenantCreated,
)
from contexts.tenants.domain.invitation import Invitation

_NOW = datetime(2026, 5, 27, tzinfo=UTC)


def _build_dgi() -> AuthorizationDgi:
    from datetime import date

    return AuthorizationDgi(number="A-001", valid_from=date(2026, 1, 1), valid_to=date(2027, 1, 1))


class TestTenant:
    def test_register_records_event(self) -> None:
        tenant = Tenant.register(
            name="Empresa A",
            ruc=Ruc("0010101800010X"),
            regime=Regime("general"),
            municipality=Municipality("Managua"),
            authorization_dgi=_build_dgi(),
            fiscal_address="Rotonda",
            is_withholder=False,
            now=_NOW,
        )
        events = tenant.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantCreated)
        assert events[0].name == "Empresa A"
        assert events[0].ruc == "0010101800010X"

    def test_update_fiscal_refreshes_timestamp(self) -> None:
        tenant = Tenant.register(
            name="Empresa A",
            ruc=Ruc("0010101800010X"),
            regime=Regime("general"),
            municipality=Municipality("Managua"),
            authorization_dgi=_build_dgi(),
            fiscal_address="A",
            is_withholder=False,
            now=_NOW,
        )
        later = _NOW + timedelta(days=1)
        tenant.update_fiscal(now=later, name="Empresa A2")
        assert tenant.name == "Empresa A2"
        assert tenant.updated_at == later

    def test_update_fiscal_rejects_ruc_keyword(self) -> None:
        tenant = Tenant.register(
            name="X",
            ruc=Ruc("0010101800010X"),
            regime=Regime("general"),
            municipality=Municipality("Managua"),
            authorization_dgi=_build_dgi(),
            fiscal_address="A",
            is_withholder=False,
            now=_NOW,
        )
        with pytest.raises(TypeError):
            tenant.update_fiscal(now=_NOW, ruc=Ruc("9999999999999Z"))  # type: ignore[call-arg]


class TestMembership:
    def test_create_owner_sets_owner_role(self) -> None:
        m = Membership.create_owner(user_id=uuid4(), tenant_id=uuid4(), now=_NOW)
        assert m.role is Role.OWNER
        assert m.status == "active"
        assert m.removed_at is None

    def test_join_rejects_owner_role(self) -> None:
        with pytest.raises(OwnerRoleNotAllowedHereError):
            Membership.join(user_id=uuid4(), tenant_id=uuid4(), role=Role.OWNER, now=_NOW)

    def test_change_role_blocks_owner_promotion(self) -> None:
        m = Membership.join(user_id=uuid4(), tenant_id=uuid4(), role=Role.ADMIN, now=_NOW)
        with pytest.raises(OwnerRoleNotAllowedHereError):
            m.change_role(new_role=Role.OWNER)

    def test_remove_flips_status(self) -> None:
        m = Membership.join(user_id=uuid4(), tenant_id=uuid4(), role=Role.ADMIN, now=_NOW)
        m.remove(now=_NOW)
        assert m.status == "removed"
        assert m.removed_at == _NOW


class TestInvitation:
    def _build(self, expires_at: datetime | None = None) -> Invitation:
        return Invitation.issue(
            tenant_id=uuid4(),
            email="x@y.io",
            proposed_role=Role.ACCOUNTANT,
            token_hash="h",
            expires_at=expires_at or (_NOW + timedelta(days=7)),
            now=_NOW,
        )

    def test_accept_flips_pending(self) -> None:
        inv = self._build()
        inv.accept(now=_NOW + timedelta(hours=1))
        assert inv.status == "accepted"

    def test_accept_rejects_expired(self) -> None:
        inv = self._build(expires_at=_NOW - timedelta(seconds=1))
        with pytest.raises(InvitationExpiredError):
            inv.accept(now=_NOW)

    def test_accept_rejects_double_accept(self) -> None:
        inv = self._build()
        inv.accept(now=_NOW)
        with pytest.raises(InvitationAlreadyAcceptedError):
            inv.accept(now=_NOW)

    def test_cancel_then_accept_fails(self) -> None:
        inv = self._build()
        inv.cancel(now=_NOW)
        with pytest.raises(InvitationCancelledError):
            inv.accept(now=_NOW)

    def test_owner_role_rejected_at_issue(self) -> None:
        with pytest.raises(ValueError):
            Invitation.issue(
                tenant_id=uuid4(),
                email="x@y.io",
                proposed_role=Role.OWNER,
                token_hash="h",
                expires_at=_NOW + timedelta(days=7),
                now=_NOW,
            )
