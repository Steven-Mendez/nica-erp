## ADDED Requirements

### Requirement: Backend coverage gate enforces ≥ 90% lines on production trees

The backend test toolchain SHALL configure `pytest-cov` such that
`make test-be-coverage` executes the test suite with line-coverage
measurement scoped to the union of:

- `apps/api/src/contexts/tenants/`
- `apps/api/src/contexts/identity/`
- `apps/api/src/shared_kernel/`

and SHALL fail the invocation when the aggregate line coverage of
the measured trees falls below 90%. `__init__.py`, files under
`tests/`, and the auto-generated Alembic env stub SHALL be
excluded from measurement.

#### Scenario: `make test-be-coverage` fails when a module drops below the gate

- **GIVEN** the suite is green and aggregate coverage is exactly
  90.0%
- **WHEN** a contributor removes a test that uniquely covered
  twelve lines in `contexts/tenants/application/use_cases/
  invite_member.py`, dropping aggregate coverage to 89.6%
- **THEN** `make test-be-coverage` SHALL exit non-zero and the
  failure SHALL name the trees and the threshold

### Requirement: Frontend coverage gate enforces ≥ 80% lines on `features/` and `components/`

The frontend test toolchain SHALL configure vitest's `v8`
coverage provider in `apps/web/vitest.config.ts` such that
`make test-fe-coverage` measures
`apps/web/src/features/**/*.{ts,tsx}` and
`apps/web/src/components/**/*.{ts,tsx}`. The auto-generated
`apps/web/src/api/schema.d.ts` and any `**/*.test.{ts,tsx}` files
SHALL be excluded. The recipe SHALL fail when measured line
coverage drops below 80%.

#### Scenario: `make test-fe-coverage` fails when a new component lands without tests

- **GIVEN** the suite is green and `features/` + `components/`
  coverage is 80.2%
- **WHEN** a contributor adds `src/components/app-shell/banner.tsx`
  (≈40 lines) with no accompanying test
- **THEN** `make test-fe-coverage` SHALL exit non-zero and the
  failure SHALL identify the offending file

### Requirement: Sprint-03 RLS isolation gate SHALL be implemented and merge-blocking

The file `apps/api/tests/e2e/contexts/tenants/test_rls_tenant_isolation.py` SHALL exist and SHALL exercise the following scenarios:

- Creation of two users (`a@test.dev`, `b@test.dev`) via the
  identity context.
- Creation of two tenants (`Empresa A`, `Empresa B`), each owned
  by the corresponding user.
- A cross-tenant peek attempt: user B (authenticated for tenant
  B) requests `GET /v1/tenants/{tenant_a_id}/invitations`, which
  SHALL respond `404` because the RLS policy filters tenant A's
  rows out of the response.
- A JWT forgery attempt: a token forged with
  `custom:active_tenant = tenant_a_id` for user B is presented;
  `GET /v1/tenants/{tenant_a_id}/members` SHALL respond `403`
  because the tenant middleware detects B is not a member of
  tenant A.

The test SHALL be marked `@pytest.mark.e2e` and SHALL run in the
default `make test-e2e` invocation.

#### Scenario: The gate is collected by pytest

- **WHEN** `pytest tests/e2e/contexts/tenants/test_rls_tenant_isolation.py --collect-only` is run
- **THEN** the collection output SHALL list the test function and
  the e2e marker

#### Scenario: The cross-tenant peek returns 404

- **GIVEN** two tenants and the authenticated user B's session
- **WHEN** `GET /v1/tenants/{tenant_a_id}/invitations` is sent
  with B's bearer token
- **THEN** the response status SHALL be `404`

#### Scenario: The forged-JWT attempt returns 403

- **GIVEN** a JWT forged to claim `custom:active_tenant = tenant_a_id`
  for user B
- **WHEN** `GET /v1/tenants/{tenant_a_id}/members` is sent with
  the forged token
- **THEN** the response status SHALL be `403`
- **AND** the response problem body SHALL include `type`
  identifying the membership-validation failure

### Requirement: Coverage thresholds are tree-scoped, not repo-global

Coverage configuration SHALL NOT impose a global repository
threshold. Each gate SHALL target a specific source tree (backend
domain code, backend identity, backend shared kernel, frontend
features, frontend components). Adding new untested code in
`apps/api/src/bootstrap/` SHALL NOT cause the backend gate to
fail.

#### Scenario: A new bootstrap helper does not perturb the backend gate

- **GIVEN** the backend gate is at exactly 90.0%
- **WHEN** a contributor adds twenty uncovered lines in
  `apps/api/src/bootstrap/settings.py`
- **THEN** `make test-be-coverage` SHALL still pass — the
  bootstrap tree is outside the measured scope
