## ADDED Requirements

### Requirement: `Email` value object validates and normalises

`contexts.identity.domain.email.Email` SHALL be a frozen dataclass with
a single `value: str` field. The constructor SHALL reject any input that
does not match a conservative `local@domain.tld` shape (at least one
`@`, at least one `.` in the domain portion, no whitespace, length ≤
254). The constructor SHALL normalise the domain portion to lowercase
(the local-part stays as supplied). `Email` SHALL NOT import
`sqlalchemy`, `fastapi`, or `boto3`.

#### Scenario: Valid email is accepted and normalised

- **WHEN** `Email("Alice@Example.COM")` is constructed
- **THEN** the resulting `value` SHALL be `"Alice@example.com"` and the
  instance SHALL compare equal to `Email("alice@example.com")` only if
  the local-part also matches (case-sensitive local-part)

#### Scenario: Malformed email is rejected at construction

- **WHEN** `Email("not-an-email")` or `Email("a@b")` is constructed
- **THEN** a `ValueError` SHALL be raised

### Requirement: `Email.parse()` classmethod is the canonical entry point

`Email.parse(value: str) -> Email` SHALL be a classmethod that trims
surrounding whitespace from `value` before delegating to the constructor.
It SHALL be the canonical entry point used by adapters and HTTP request
models when converting raw strings (form input, JWT claims, JSON bodies)
into the value object — direct construction via `Email(...)` is allowed
but `parse()` is the recommended call site so the trim-and-validate
pipeline is consistent. `parse()` SHALL raise `ValueError` on any input
the constructor would reject after trimming.

#### Scenario: Surrounding whitespace is trimmed

- **WHEN** `Email.parse("  alice@example.com  ")` is called
- **THEN** the resulting `value` SHALL equal `"alice@example.com"` (no
  leading or trailing whitespace)

#### Scenario: Invalid input still raises

- **WHEN** `Email.parse("   not-an-email   ")` is called
- **THEN** a `ValueError` SHALL be raised after trimming

### Requirement: `Password` value object enforces the platform policy

`contexts.identity.domain.password.Password` SHALL hold the raw secret
in `value: str` and expose `validate_policy()` raising
`PasswordPolicyError` (a `ValueError` subclass) when **any** of the
following fails: length ≥ 12, ≥1 uppercase ASCII letter, ≥1 lowercase
ASCII letter, ≥1 digit, ≥1 symbol from `!@#$%^&*()_+\-=[]{}|;:,.<>?/`.
`Password` MUST NOT log or expose its `value` in `__repr__`.

#### Scenario: Compliant password passes

- **WHEN** `Password("Demo1234!@xy")` is constructed and `validate_policy()` is called
- **THEN** the call SHALL return `None` without raising

#### Scenario: Short password is rejected

- **WHEN** `Password("Demo1!").validate_policy()` is called
- **THEN** `PasswordPolicyError` SHALL be raised

#### Scenario: Missing character class is rejected

- **WHEN** `Password("alllowercase123!").validate_policy()` is called
  (no uppercase)
- **THEN** `PasswordPolicyError` SHALL be raised

#### Scenario: `repr` does not leak the secret

- **WHEN** `repr(Password("Demo1234!@xy"))` is evaluated
- **THEN** the resulting string MUST NOT contain `"Demo1234!@xy"`

### Requirement: `User` aggregate captures profile and events

`contexts.identity.domain.user.User` SHALL extend
`shared_kernel.domain.AggregateRoot[UUID]` and expose the fields
`external_sub: str`, `email: Email`, `display_name: str`,
`locale: str`, `timezone: str`, `preferences: dict[str, Any]`,
`created_at: datetime`, `updated_at: datetime`. A class method
`register(external_sub, email, *, now)` SHALL build a new aggregate
with `display_name=""`, `locale="es-NI"`, `timezone="America/Managua"`,
`preferences={}`, both timestamps equal to `now`, and SHALL record a
`UserRegistered` event before returning. `update_profile(...)` SHALL
mutate `display_name`, `locale`, `timezone`, `preferences` and refresh
`updated_at`.

#### Scenario: `register` records `UserRegistered` exactly once

- **WHEN** `User.register(external_sub="abc", email=Email("a@b.io"), now=t)` is called
- **THEN** `pull_events()` on the result SHALL return a single
  `UserRegistered` whose `user_id` matches the aggregate id and whose
  `registered_at` equals `t`

### Requirement: `UserRegistered` and `PasswordReset` are versioned domain events

`UserRegistered` and `PasswordReset` SHALL be frozen kw-only
`DomainEvent` subclasses. `UserRegistered` SHALL carry `user_id: UUID`,
`email: str`, and `registered_at: datetime` (UTC). `PasswordReset`
SHALL carry `user_id: UUID` and `reset_at: datetime` (UTC). Their
event names emitted to the outbox SHALL be `identity.UserRegistered`
and `identity.PasswordReset` respectively, with `event_version=1`
([ADR-0012](../../../../docs/adr/0012-event-versioning.md)).

#### Scenario: Event metadata defaults are populated

- **WHEN** `UserRegistered(user_id=u, email="a@b.io", registered_at=t)`
  is constructed
- **THEN** the instance SHALL also expose a non-empty `event_id: UUID`
  and an `occurred_at: datetime` in UTC

#### Scenario: Event is immutable after construction

- **WHEN** code attempts to reassign `email` on an existing
  `UserRegistered` instance
- **THEN** the assignment SHALL raise an error
