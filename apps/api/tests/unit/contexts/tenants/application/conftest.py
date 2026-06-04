"""Shared fakes for tenants application-layer unit tests."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.identity.application.ports.outbound import Identity, IdentityProvider
from contexts.tenants.application.ports.outbound import (
    InvitationTokenClaims,
    InvitationTokenIssued,
)
from contexts.tenants.domain import (
    AuthorizationDgi,
    Invitation,
    Membership,
    Role,
    Tenant,
)


class FakeUow:
    """Minimal ``UnitOfWork`` stand-in tracking commit/rollback."""

    def __init__(self) -> None:
        self.begin_count = 0
        self.committed = False
        self.rolled_back = False

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[Any]:
        self.begin_count += 1
        try:
            yield None
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@dataclass
class FakeTenantRepository:
    by_id: dict[UUID, Tenant] = field(default_factory=dict)
    by_ruc: dict[str, Tenant] = field(default_factory=dict)
    add_count: int = 0
    update_count: int = 0

    async def get(self, tenant_id: UUID) -> Tenant | None:
        return self.by_id.get(tenant_id)

    async def get_by_ruc(self, ruc: str) -> Tenant | None:
        return self.by_ruc.get(ruc)

    async def add(self, tenant: Tenant) -> None:
        self.by_id[tenant.id] = tenant
        self.by_ruc[tenant.ruc.value] = tenant
        self.add_count += 1

    async def update(self, tenant: Tenant) -> None:
        self.by_id[tenant.id] = tenant
        self.update_count += 1

    async def list_for_user(self, user_id: UUID) -> list[Tenant]:
        return list(self.by_id.values())


@dataclass
class FakeMembershipRepository:
    rows: list[Membership] = field(default_factory=list)
    add_count: int = 0
    update_count: int = 0

    async def add(self, membership: Membership) -> None:
        self.rows.append(membership)
        self.add_count += 1

    async def update(self, membership: Membership) -> None:
        # Match by id and replace in place.
        for i, existing in enumerate(self.rows):
            if existing.id == membership.id:
                self.rows[i] = membership
                break
        self.update_count += 1

    async def find(self, *, user_id: UUID, tenant_id: UUID) -> Membership | None:
        for m in self.rows:
            if m.user_id == user_id and m.tenant_id == tenant_id:
                return m
        return None

    async def list_by_tenant(self, tenant_id: UUID) -> list[Membership]:
        return [m for m in self.rows if m.tenant_id == tenant_id]

    async def list_active_for_user(self, user_id: UUID) -> list[Membership]:
        return [m for m in self.rows if m.user_id == user_id and m.status == "active"]

    async def list_page(self, query: Any) -> tuple[list[Any], int]:
        # Filter by tenant and the optional role/status sets; ignore
        # `q` here (the SQL adapter owns LIKE semantics). Tests that
        # need q-matching exercise the integration test instead.
        from contexts.tenants.application.use_cases.list_members import MemberView

        rows = [m for m in self.rows if m.tenant_id == query.tenant_id]
        if len(query.roles) > 0:
            role_values = {r.value for r in query.roles}
            rows = [m for m in rows if m.role.value in role_values]
        if len(query.statuses) > 0:
            status_values = set(query.statuses)
            rows = [m for m in rows if m.status in status_values]
        total = len(rows)
        page = rows[query.offset : query.offset + query.limit]
        views = [
            MemberView(
                id=m.id,
                user_id=m.user_id,
                tenant_id=m.tenant_id,
                role=m.role,
                status=m.status,
                joined_at=m.joined_at,
                removed_at=m.removed_at,
                display_name=None,
                email=None,
            )
            for m in page
        ]
        return views, total


@dataclass
class FakeInvitationRepository:
    by_id: dict[UUID, Invitation] = field(default_factory=dict)
    by_token_hash: dict[str, Invitation] = field(default_factory=dict)
    add_count: int = 0
    update_count: int = 0

    async def add(self, invitation: Invitation) -> None:
        self.by_id[invitation.id] = invitation
        self.by_token_hash[invitation.token_hash] = invitation
        self.add_count += 1

    async def update(self, invitation: Invitation) -> None:
        self.by_id[invitation.id] = invitation
        self.update_count += 1

    async def get(self, invitation_id: UUID) -> Invitation | None:
        return self.by_id.get(invitation_id)

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        return self.by_token_hash.get(token_hash)

    async def list_by_tenant(self, tenant_id: UUID) -> list[Invitation]:
        return [i for i in self.by_id.values() if i.tenant_id == tenant_id]

    async def list_pending_by_email(self, tenant_id: UUID, email: str) -> list[Invitation]:
        needle = email.lower()
        return [
            i
            for i in self.by_id.values()
            if i.tenant_id == tenant_id and i.email.lower() == needle and i.status == "pending"
        ]


@dataclass
class FakeOutbox:
    rows: list[dict[str, Any]] = field(default_factory=list)

    async def append(
        self,
        *,
        event_id: UUID,
        event_type: str,
        event_version: int,
        aggregate_type: str,
        aggregate_id: UUID,
        tenant_id: UUID | None,
        payload: dict[str, Any],
    ) -> None:
        self.rows.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "event_version": event_version,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "tenant_id": tenant_id,
                "payload": payload,
            }
        )


@dataclass
class FakeInvitationTokenGenerator:
    """Deterministic token generator for tests.

    ``mint`` returns ``"token-<email>-<tenant>"`` and the corresponding
    SHA-256 hash; ``verify`` is a no-op (any token is "valid");
    ``hash`` rehashes the raw token. This is enough for use-case tests
    that exercise the ``token_hash`` lookup path.
    """

    ttl: timedelta = timedelta(days=7)

    def mint(
        self,
        *,
        tenant_id: UUID,
        email: str,
        proposed_role: Role,
        now: datetime,
    ) -> InvitationTokenIssued:
        token = f"token-{email}-{tenant_id}"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return InvitationTokenIssued(
            token=token,
            token_hash=token_hash,
            expires_at=now + self.ttl,
        )

    def verify(self, *, token: str) -> InvitationTokenClaims:
        # Match the email baked into ``mint`` output so the use case's
        # identity-binding check resolves to the test's default user.
        # Tests that need a mismatch override ``token_generator.verify``.
        return InvitationTokenClaims(
            tenant_id=uuid4(),
            email="invitee@test.dev",
            proposed_role=Role.VIEWER,
            expires_at=datetime.now(UTC) + self.ttl,
        )

    def hash(self, *, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class FakeEmailSender:
    sent: list[dict[str, str]] = field(default_factory=list)

    async def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text})


@dataclass
class FakeIdentityProvider(IdentityProvider):
    refresh_token_value: str = "new-refresh"
    access_token_value: str = "new-access"
    id_token_value: str = "new-id"
    update_active_tenant_calls: list[tuple[str, str]] = field(default_factory=list)

    async def register(self, *, email: str, password: str) -> str:
        return str(uuid4())

    async def confirm_signup(self, *, email: str, code: str) -> str:
        return str(uuid4())

    async def resend_code(self, *, email: str) -> None:
        return None

    async def authenticate(self, *, email: str, password: str) -> Identity:
        return Identity(
            sub=str(uuid4()),
            email="probe@test.dev",
            access_token=self.access_token_value,
            refresh_token=self.refresh_token_value,
            id_token=self.id_token_value,
        )

    async def verify_token(self, *, token: str) -> dict[str, Any]:
        return {"sub": str(uuid4()), "email": "probe@test.dev"}

    async def refresh(self, *, refresh_token: str) -> Identity:
        return Identity(
            sub=str(uuid4()),
            email="probe@test.dev",
            access_token=self.access_token_value,
            refresh_token=self.refresh_token_value,
            id_token=self.id_token_value,
        )

    async def global_signout(self, *, external_sub: str) -> None:
        return None

    async def update_active_tenant(self, *, external_sub: str, tenant_id: str) -> None:
        self.update_active_tenant_calls.append((external_sub, tenant_id))

    async def forgot_password(self, *, email: str) -> None:
        return None

    async def confirm_forgot_password(self, *, email: str, code: str, new_password: str) -> None:
        return None

    async def change_password(
        self,
        *,
        access_token: str,
        previous_password: str,
        proposed_password: str,
    ) -> None:
        return None


# --- Fixtures -------------------------------------------------------------


@pytest.fixture
def fake_uow() -> Iterator[FakeUow]:
    yield FakeUow()


@pytest.fixture
def tenant_repo() -> Iterator[FakeTenantRepository]:
    yield FakeTenantRepository()


@pytest.fixture
def membership_repo() -> Iterator[FakeMembershipRepository]:
    yield FakeMembershipRepository()


@pytest.fixture
def invitation_repo() -> Iterator[FakeInvitationRepository]:
    yield FakeInvitationRepository()


@pytest.fixture
def outbox() -> Iterator[FakeOutbox]:
    yield FakeOutbox()


@pytest.fixture
def token_generator() -> Iterator[FakeInvitationTokenGenerator]:
    yield FakeInvitationTokenGenerator()


@pytest.fixture
def email_sender() -> Iterator[FakeEmailSender]:
    yield FakeEmailSender()


@pytest.fixture
def identity_provider() -> Iterator[FakeIdentityProvider]:
    yield FakeIdentityProvider()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def seeded_tenant(
    tenant_repo: FakeTenantRepository,
    fixed_now: datetime,
) -> Tenant:
    """Insert a baseline tenant into the fake repo and return it."""

    from contexts.tenants.domain import Municipality, Regime, Ruc

    tenant = Tenant.register(
        name="Empresa A",
        ruc=Ruc.parse("0010101800010X"),
        regime=Regime("general"),
        municipality=Municipality("Managua"),
        authorization_dgi=AuthorizationDgi(
            number="A-001",
            valid_from=fixed_now.date(),
            valid_to=fixed_now.date().replace(year=fixed_now.year + 1),
        ),
        fiscal_address="Rotonda Centroamérica, Managua",
        is_withholder=False,
        now=fixed_now,
        id_=uuid4(),
    )
    tenant_repo.by_id[tenant.id] = tenant
    tenant_repo.by_ruc[tenant.ruc.value] = tenant
    return tenant
