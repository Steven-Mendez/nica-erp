# Backend Test Quality Guards

## ADDED Requirements

### Requirement: Triad-respecting test lanes

The Makefile SHALL expose one recipe per triad layer so contributors
can run the cheapest layer first without paying the cost of the
slower layers.

#### Scenario: Unit lane runs only `tests/unit/`

- **WHEN** a contributor runs `make test-be-unit`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/unit`
- **AND** the run SHALL NOT spin up the Postgres testcontainer
- **AND** the run SHALL complete in under five seconds on a warm
  cache

#### Scenario: Integration lane runs only `tests/integration/`

- **WHEN** a contributor runs `make test-be-integration`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/integration`
- **AND** the Postgres testcontainer SHALL boot exactly once for
  the session

#### Scenario: E2E lane runs only `tests/e2e/`

- **WHEN** a contributor runs `make test-be-e2e`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/e2e`

### Requirement: Property-based coverage of domain value objects

Every value object in `contexts/identity/domain` and
`contexts/tenants/domain` whose constructor validates input
SHALL be exercised by a Hypothesis property test that searches the
input space.

#### Scenario: `Password.validate_policy` is searched, not sampled

- **WHEN** the unit suite runs
- **THEN** a Hypothesis strategy SHALL generate strings that match
  the policy and assert `validate_policy()` returns without raising
- **AND** a second strategy SHALL generate strings that violate at
  least one rule and assert `PasswordPolicyError` is raised
- **AND** a third test SHALL assert that for any string `s`,
  `s not in repr(Password(s))`

#### Scenario: `Ruc.parse` is searched, not sampled

- **WHEN** the unit suite runs
- **THEN** a Hypothesis strategy SHALL generate strings matching
  `\d{13}[A-Z]` (with optional surrounding whitespace) and assert
  `Ruc.parse(s).value == s.strip()`
- **AND** a second strategy SHALL generate strings that fail the
  regex and assert `ValueError` is raised

#### Scenario: `Municipality` accepts exactly the catalog

- **WHEN** the unit suite runs
- **THEN** a Hypothesis `sampled_from(KNOWN_MUNICIPALITIES)`
  strategy SHALL assert every catalogued name constructs without
  error
- **AND** a `text()` strategy filtered against the catalog SHALL
  assert non-catalogued strings raise `ValueError`

#### Scenario: `Regime` accepts exactly `{"general", "simplified"}`

- **WHEN** the unit suite runs
- **THEN** the two valid literals SHALL both construct without
  error
- **AND** any other string SHALL raise `ValueError`

### Requirement: Schema-vs-ORM consistency guard

The integration suite SHALL fail when the Postgres schema and
the SQLAlchemy ORM mappers diverge.

#### Scenario: Every mapped column exists in the DB

- **WHEN** `tests/integration/shared_kernel/test_schema_consistency.py`
  runs
- **AND** the session-scoped `_run_migrations` fixture has applied
  `alembic upgrade head`
- **THEN** the test SHALL iterate every column declared on every
  mapper attached to `Base.metadata` whose `__table_args__` does
  not set `info={"managed_externally": True}`
- **AND** the test SHALL assert a column with the same name and
  nullability exists in `information_schema.columns` for the same
  `(table_schema, table_name)`
- **AND** the failure message SHALL name `<table>.<column>` and
  state which side declared it

### Requirement: Direct RLS-policy enforcement guard

The integration suite SHALL fail when the Postgres RLS policy on
`tenant_members` or `invitations` stops enforcing the per-tenant
filter, even when the HTTP middleware is absent.

#### Scenario: Cross-tenant SELECT returns zero rows under `nica_erp_app`

- **WHEN** `tests/integration/contexts/tenants/test_rls_policy_enforcement.py`
  runs
- **AND** tenants A and B have been seeded each with one row in
  `tenant_members` and `invitations` via a superuser engine
- **AND** an `AsyncSession` is opened as the `nica_erp_app` role
- **AND** `SET LOCAL app.tenant_id` has been called with tenant B's
  id
- **THEN** `SELECT id FROM tenant_members` SHALL return exactly the
  row tagged with tenant B
- **AND** the same SELECT on `invitations` SHALL return exactly the
  row tagged with tenant B
- **AND** repeating both SELECTs with tenant A's id SHALL return
  exactly tenant A's rows

#### Scenario: Missing `app.tenant_id` returns zero rows

- **WHEN** the same suite resets `app.tenant_id` to `''`
  (the default for `current_setting(..., true)`)
- **THEN** `SELECT id FROM tenant_members` SHALL return zero rows
- **AND** the same SELECT on `invitations` SHALL return zero rows

### Requirement: Shared `_factories/` package for domain object builders

A `tests/_factories/` package SHALL hold canonical builders for
domain objects and DB seed helpers, so tests do not duplicate
construction boilerplate.

#### Scenario: `make_password` returns a policy-satisfying Password

- **WHEN** a test imports `from tests._factories.identity import
  make_password`
- **THEN** `make_password()` SHALL return a `Password` whose
  `validate_policy()` returns without raising
- **AND** the default value SHALL be the same canonical literal
  the e2e suite uses (`E2E_PASSWORD`) so identity flows stay
  cross-layer consistent

#### Scenario: `seed_tenant_row` returns the new tenant's id

- **WHEN** a test calls `seed_tenant_row(session, name="Acme")`
- **THEN** the helper SHALL `INSERT` a row into `tenants` with the
  given name and sensible defaults for fiscal fields
- **AND** the return value SHALL be the inserted tenant's `id`
- **AND** the helper SHALL commit through the session it was
  given so the row is visible to subsequent statements in the
  same transaction

### Requirement: Unit coverage for read-only use cases

`ListMembers` and `ListInvitations` SHALL each have a unit test
that asserts their UoW + repository contract, so a future change
to the use-case signature surfaces in CI before it surfaces in a
500 from the corresponding HTTP route.

#### Scenario: `ListMembers.execute` opens the UoW and returns the repository result

- **WHEN** `tests/unit/contexts/tenants/application/test_list_members.py`
  runs
- **THEN** the test SHALL inject a fake `UnitOfWork` and a fake
  `MembershipRepository`
- **AND** the test SHALL assert the repository's
  `list_by_tenant(tenant_id)` was awaited with the same tenant id
  the use case received
- **AND** the test SHALL assert the value returned by the use case
  is identical to the value returned by the fake repository

#### Scenario: `ListInvitations.execute` opens the UoW and returns the repository result

- **WHEN** `tests/unit/contexts/tenants/application/test_list_invitations.py`
  runs
- **THEN** the test SHALL inject a fake `UnitOfWork` and a fake
  `InvitationRepository`
- **AND** the same UoW / passthrough assertions SHALL hold
