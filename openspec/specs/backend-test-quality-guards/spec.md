# backend-test-quality-guards Specification

## Purpose

The backend test triad (unit / integration / e2e) holds *defect-finding
power* in addition to *coverage*. Every domain value object is searched
across its input space by `hypothesis`; every repository's column list
is verified against the migrated schema; the Postgres RLS policy is
verified at the database layer in addition to the HTTP layer. A
`tests/_factories/` package supplies canonical domain object builders
and RLS-compliant row seeders so new tests do not duplicate construction
boilerplate. A parametrized Makefile recipe
(`make test SCOPE=be LANE=unit|integration|e2e`) lets contributors run
the cheapest layer first without paying the testcontainer boot cost.

## Requirements

### Requirement: Triad-respecting test lanes

The Makefile SHALL expose a single parametrized recipe so
contributors can run the cheapest layer first without paying
the cost of the slower layers. The recipe SHALL accept a
`SCOPE` variable (`be` to restrict to the backend) and a
`LANE` variable (`unit`, `integration`, or `e2e`) and SHALL
translate `LANE=<lane>` into a pytest invocation that targets
only the matching directory under `apps/api/tests/`.

#### Scenario: Unit lane runs only `tests/unit/`

- **WHEN** a contributor runs `make test SCOPE=be LANE=unit`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/unit`
- **AND** the run SHALL NOT spin up the Postgres testcontainer
- **AND** the run SHALL complete in under ten seconds on a warm
  cache

#### Scenario: Integration lane runs only `tests/integration/`

- **WHEN** a contributor runs `make test SCOPE=be LANE=integration`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/integration`
- **AND** the Postgres testcontainer SHALL boot exactly once for
  the session

#### Scenario: E2E lane runs only `tests/e2e/`

- **WHEN** a contributor runs `make test SCOPE=be LANE=e2e`
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
  `repr(Password(s)) == "Password(***)"` exactly — the constant
  literal is the invariant, not "`s not in repr(...)`"
  (the masked literal itself contains `*`)

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

### Requirement: Schema-vs-repository consistency guard

The integration suite SHALL fail when the Postgres schema and a
repository's `_COLUMNS` constant diverge.

#### Scenario: Every column referenced by a repository exists in the DB

- **WHEN** `tests/integration/shared_kernel/test_schema_consistency.py`
  runs
- **AND** the session-scoped `_run_migrations` fixture has applied
  `alembic upgrade head`
- **THEN** the test SHALL iterate every name parsed from each
  repository's `_COLUMNS` constant (plus an explicit list for
  ``users``, whose ``user_repository`` uses inline SQL)
- **AND** the test SHALL assert a column with the same name exists
  in `information_schema.columns` for the same
  `(table_schema, table_name)`
- **AND** the failure message SHALL name the missing
  `<table>.<column>` and state that either the migration is
  incomplete or the repository SQL drifted past the schema

### Requirement: Direct RLS-policy enforcement guard

The integration suite SHALL fail when the Postgres RLS policy on
`tenant_members` or `invitations` stops enforcing the per-tenant
filter, even when the HTTP middleware is absent.

#### Scenario: Cross-tenant SELECT returns the right rows under `nica_erp_app`

- **WHEN** `tests/integration/contexts/tenants/test_rls_policy_enforcement.py`
  runs
- **AND** tenants A and B have been seeded each with one row in
  `tenant_members` and `invitations` via the seed helpers
- **AND** an `AsyncSession` is opened as the `nica_erp_app` role
- **AND** `app.tenant_id` has been set to tenant B's id
- **THEN** `SELECT id FROM tenant_members` SHALL return exactly the
  row tagged with tenant B
- **AND** the same SELECT on `invitations` SHALL return exactly the
  row tagged with tenant B
- **AND** repeating both SELECTs with tenant A's id SHALL return
  exactly tenant A's rows

#### Scenario: Zero-UUID sentinel hides every real row

- **WHEN** the same suite sets `app.tenant_id` to
  `'00000000-0000-0000-0000-000000000000'` (the production
  sentinel for "no tenant active", see
  ``bootstrap/container.py._ZERO_UUID``)
- **THEN** `SELECT id FROM invitations` SHALL return zero rows

#### Scenario: `nica_erp_app` is NOBYPASSRLS

- **WHEN** the same suite queries
  `SELECT rolbypassrls FROM pg_roles WHERE rolname='nica_erp_app'`
- **THEN** the value SHALL be `false`. If a migration flips it,
  every RLS test would silently pass — this guard catches that
  posture regression directly.

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
  the e2e suite uses (`E2E_PASSWORD` / `CANONICAL_PASSWORD`) so
  identity flows stay cross-layer consistent

#### Scenario: `seed_tenant_row` returns the new tenant's id

- **WHEN** a test calls `seed_tenant_row(session, name="Acme")`
- **THEN** the helper SHALL `INSERT` a row into `tenants` with the
  given name and sensible defaults for fiscal fields
- **AND** the return value SHALL be the inserted tenant's `id`
- **AND** the caller SHALL be responsible for committing the
  session (so multiple seeders can compose in one transaction)

#### Scenario: `seed_membership_row` sets the GUC before INSERT

- **WHEN** a test calls
  `seed_membership_row(session, tenant_id=tid, user_id=uid)`
- **THEN** the helper SHALL `SELECT set_config('app.tenant_id',
  tid, true)` before the INSERT so the RLS ``WITH CHECK`` policy
  on ``tenant_members`` passes under `nica_erp_app`
- **AND** the helper SHALL return the inserted membership's `id`

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
- **AND** the test SHALL assert the result equals the repository's
  filtered output for the requested tenant id
- **AND** the test SHALL assert the UoW was entered exactly once
  and committed

#### Scenario: `ListInvitations.execute` opens the UoW and returns the repository result

- **WHEN** `tests/unit/contexts/tenants/application/test_list_invitations.py`
  runs
- **THEN** the test SHALL inject a fake `UnitOfWork` and a fake
  `InvitationRepository`
- **AND** the same UoW / passthrough assertions SHALL hold
