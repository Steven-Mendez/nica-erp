## ADDED Requirements

### Requirement: `Ruc` value object validates Nicaragua RUC format

`contexts.tenants.domain.ruc.Ruc` SHALL be a frozen dataclass with a
single `value: str` field. The constructor SHALL reject any input
that does not match the structural Nicaragua RUC shape: exactly 14
characters drawn from digits `0-9` and the uppercase letter suffix
the DGI uses (e.g. `0010101800010X`). Whitespace SHALL be trimmed
prior to validation. `Ruc` SHALL NOT import `sqlalchemy`, `fastapi`,
or `boto3`.

#### Scenario: Valid RUC is accepted

- **WHEN** `Ruc.parse("0010101800010X")` is called
- **THEN** the resulting `value` SHALL equal `"0010101800010X"`

#### Scenario: Malformed RUC is rejected at construction

- **WHEN** `Ruc.parse("123")` or `Ruc.parse("0010101800010")` (13
  characters) is called
- **THEN** a `ValueError` SHALL be raised

### Requirement: `Municipality` value object is enum-like over a catalog

`contexts.tenants.domain.municipality.Municipality` SHALL be a
frozen dataclass with `value: str`. The module SHALL expose
`KNOWN_MUNICIPALITIES: frozenset[str]` containing at least the
seventeen Nicaragua departmental capitals (Managua, León, Granada,
Masaya, Estelí, Matagalpa, etc.). The constructor SHALL reject any
value not in `KNOWN_MUNICIPALITIES`. The catalog is extensible —
adding a municipality is a code change, not a runtime mutation.

#### Scenario: Known municipality is accepted

- **WHEN** `Municipality("Managua")` is constructed
- **THEN** the resulting `value` SHALL equal `"Managua"`

#### Scenario: Unknown municipality is rejected

- **WHEN** `Municipality("Atlantis")` is constructed
- **THEN** a `ValueError` SHALL be raised

### Requirement: `Regime` value object is a closed literal

`contexts.tenants.domain.regime.Regime` SHALL be a frozen dataclass
whose `value` SHALL be one of `"general"` or `"simplified"`. Any
other value SHALL raise `ValueError` at construction.

#### Scenario: `general` is accepted

- **WHEN** `Regime("general")` is constructed
- **THEN** the resulting `value` SHALL equal `"general"`

#### Scenario: Unknown regime is rejected

- **WHEN** `Regime("custom")` is constructed
- **THEN** a `ValueError` SHALL be raised

### Requirement: `AuthorizationDgi` value object enforces date ordering

`contexts.tenants.domain.authorization_dgi.AuthorizationDgi` SHALL
be a frozen dataclass with `number: str`, `valid_from: date`,
`valid_to: date`. The constructor SHALL reject when `valid_to <
valid_from`. `number` MAY be empty in MVP (tenants without active
DGI authorization yet), but if non-empty SHALL be at most 32
characters.

#### Scenario: Valid range is accepted

- **WHEN** `AuthorizationDgi(number="A-001", valid_from=date(2026,1,1), valid_to=date(2027,1,1))` is constructed
- **THEN** the instance SHALL hold the same values

#### Scenario: Reversed range is rejected

- **WHEN** `AuthorizationDgi(number="A-001", valid_from=date(2027,1,1), valid_to=date(2026,1,1))` is constructed
- **THEN** a `ValueError` SHALL be raised

### Requirement: `Role` is a closed enum with stable ordinals

`contexts.tenants.domain.role.Role` SHALL be a `StrEnum` with members
`OWNER="owner"`, `ADMIN="admin"`, `ACCOUNTANT="accountant"`,
`SALESPERSON="salesperson"`, `VIEWER="viewer"`. `Role.from_str()`
SHALL raise `ValueError` on unknown input. The order of declaration
SHALL match the privilege descent
`owner > admin > accountant > salesperson > viewer`.

#### Scenario: `Role.from_str("admin")` resolves

- **WHEN** `Role.from_str("admin")` is called
- **THEN** the returned value SHALL be `Role.ADMIN`

#### Scenario: Unknown role is rejected

- **WHEN** `Role.from_str("god")` is called
- **THEN** a `ValueError` SHALL be raised

### Requirement: `Tenant` aggregate captures fiscal metadata and lifecycle

`contexts.tenants.domain.tenant.Tenant` SHALL extend
`shared_kernel.domain.AggregateRoot[UUID]` with fields `name: str`,
`ruc: Ruc`, `regime: Regime`, `municipality: Municipality`,
`authorization_dgi: AuthorizationDgi`, `fiscal_address: str`,
`is_withholder: bool`, `status: str`, `created_at: datetime`,
`updated_at: datetime`. A class method
`register(*, name, ruc, regime, municipality, authorization_dgi,
fiscal_address, is_withholder, now)` SHALL build a new aggregate
with `status="active"`, both timestamps equal to `now`, and SHALL
record a `TenantCreated v1` event before returning. An instance
method `update_fiscal(*, name=None, regime=None, municipality=None,
authorization_dgi=None, fiscal_address=None, is_withholder=None,
now)` SHALL mutate the supplied subset and refresh `updated_at`.
`Tenant.ruc` SHALL be immutable once set (the constructor accepts
it, `update_fiscal` rejects it).

#### Scenario: `register` records `TenantCreated`

- **WHEN** `Tenant.register(...)` is called with valid VOs
- **THEN** `pull_events()` on the result SHALL contain a single
  `TenantCreated` whose `tenant_id` matches the aggregate id and
  whose `name`, `ruc`, `municipality` fields match the inputs

#### Scenario: `update_fiscal` cannot mutate RUC

- **WHEN** code attempts to pass `ruc=` to `update_fiscal(...)`
- **THEN** a `TypeError` SHALL be raised (the method signature does
  not accept the keyword)

### Requirement: `Membership` entity restricts owner construction

`contexts.tenants.domain.membership.Membership` SHALL be a dataclass
with `user_id: UUID`, `tenant_id: UUID`, `role: Role`,
`status: str` (`active`/`removed`), `joined_at: datetime`,
`removed_at: datetime | None`. The factory classmethod
`create_owner(*, user_id, tenant_id, now)` SHALL be the ONLY
constructor that sets `role=Role.OWNER`. Any direct construction
attempt that passes `role=Role.OWNER` outside `create_owner` SHALL
raise `OwnerRoleNotAllowedHereError`.

#### Scenario: `create_owner` produces an owner membership

- **WHEN** `Membership.create_owner(user_id=u, tenant_id=t, now=ts)`
  is called
- **THEN** the result SHALL have `role=Role.OWNER`, `status='active'`,
  `joined_at=ts`, `removed_at=None`

#### Scenario: Direct `Membership(role=OWNER, ...)` fails

- **WHEN** `Membership(user_id=u, tenant_id=t, role=Role.OWNER,
  status='active', joined_at=ts, removed_at=None)` is constructed
- **THEN** `OwnerRoleNotAllowedHereError` SHALL be raised

### Requirement: `Invitation` entity tracks lifecycle and rejects double-accept

`contexts.tenants.domain.invitation.Invitation` SHALL be a dataclass
with `tenant_id: UUID`, `email: str`, `proposed_role: Role`,
`token_hash: str`, `expires_at: datetime`, `status: str`
(`pending`/`accepted`/`cancelled`/`expired`), `cancelled_at:
datetime | None`, `created_at: datetime`. Instance methods:

- `accept(now)` flips `status='pending' → 'accepted'`; raises
  `InvitationExpiredError` when `now > expires_at`,
  `InvitationAlreadyAcceptedError` when `status='accepted'`,
  `InvitationCancelledError` when `status='cancelled'`.
- `cancel(now)` flips `status='pending' → 'cancelled'` and sets
  `cancelled_at=now`; raises `InvitationAlreadyAcceptedError` when
  already accepted (cancelling an accepted invitation is a no-op
  with an audit trail belonging to membership removal).

`Invitation` SHALL NOT carry the plaintext token — only the hash.

#### Scenario: `accept` flips a pending invitation

- **WHEN** a `pending` invitation with `expires_at > now` is
  `.accept(now)`-ed
- **THEN** its `status` SHALL be `'accepted'` and the method
  SHALL NOT raise

#### Scenario: `accept` rejects an expired invitation

- **WHEN** a `pending` invitation with `expires_at < now` is
  `.accept(now)`-ed
- **THEN** `InvitationExpiredError` SHALL be raised

### Requirement: Six domain events are versioned and immutable

`contexts.tenants.domain.events` SHALL declare frozen kw-only
`DomainEvent` subclasses for `TenantCreated v1` (`tenant_id`,
`name`, `ruc`, `municipality`, `created_at`),
`MemberInvited v1` (`tenant_id`, `invitation_id`, `email`,
`proposed_role`, `invited_at`),
`MemberJoined v1` (`tenant_id`, `user_id`, `role`, `joined_at`),
`MemberRemoved v1` (`tenant_id`, `user_id`, `removed_at`),
`InvitationCancelled v1` (`tenant_id`, `invitation_id`,
`cancelled_at`),
`MemberRoleChanged v1` (`tenant_id`, `user_id`, `old_role`,
`new_role`, `changed_at`). Event names emitted to the outbox SHALL
be `tenants.<EventName>` with `event_version=1`
([ADR-0012](../../../../docs/adr/0012-event-versioning.md)).

#### Scenario: Event metadata defaults are populated

- **WHEN** `TenantCreated(tenant_id=t, name="X", ruc="0010101800010X",
  municipality="Managua", created_at=ts)` is constructed
- **THEN** the instance SHALL also expose a non-empty `event_id:
  UUID` and `occurred_at: datetime` in UTC

#### Scenario: Event is immutable after construction

- **WHEN** code attempts to reassign `name` on an existing
  `TenantCreated`
- **THEN** the assignment SHALL raise `FrozenInstanceError`
