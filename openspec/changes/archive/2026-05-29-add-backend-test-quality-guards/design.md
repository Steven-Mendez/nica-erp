## Context

This change stacks on top of
[`test-backfill-and-e2e-tooling`](../test-backfill-and-e2e-tooling/proposal.md).
That change raises *line coverage*; this one raises
*defect-finding power* without inflating coverage further. The
two are complementary — a single trivial property test bumps
coverage by < 1 % but can cover an entire input space.

The relevant architectural envelope is fixed by:

- `docs/04-testing-strategy.md` — the triad
  (unit / integration / e2e) and the rule that each layer tests
  what is appropriate for it (no DB in unit, no real network in
  integration except the testcontainer, real HTTP in e2e).
- [`feedback_test_layout`](file:///Users/wern/.claude/projects/-Users-wern-Documents-GitHub-nica-erp/memory/feedback_test_layout.md)
  — tests live under `apps/api/tests/{unit,integration,e2e}/`
  mirroring `src/`, never co-located. The new `_factories/`
  package lives directly under `tests/` because it is consumed
  by all three layers and belongs to none.

## Goals / Non-Goals

**Goals**

- Every domain value object in `contexts/identity` and
  `contexts/tenants` has a property test that searches the
  input space, not a handful of hand-picked examples.
- Schema drift between Alembic migrations and SQLAlchemy
  mappers fails CI before the next migration lands.
- The Postgres RLS posture (`FORCE ROW LEVEL SECURITY`,
  `nica_erp_app` NOBYPASSRLS, the per-tenant policy bodies) is
  asserted at the database layer, not just through the HTTP
  middleware.
- Contributors can run the cheapest test lane first
  (`make test-be-unit`, < 2 s) without paying the testcontainer
  boot cost.

**Non-Goals**

- No mutation testing in this sprint. Mutation testing measures
  test power directly, but its CI cost (full suite per mutant)
  is prohibitive before the property layer settles. Revisit
  once Hypothesis has been in place for a sprint and the test
  suite has stabilised.
- No `schemathesis`-style auto-generated HTTP contract tests.
  The OpenAPI schema is generated *from* the same FastAPI
  routes whose behaviour we'd be checking; the round-trip
  catches almost nothing real. A future change can add
  schemathesis once contracts are owned externally (e.g. an
  SDK or partner integration).
- No fuzzing of the JWT verifier or password hasher. Both
  delegate to vetted libraries (`PyJWT`, `bcrypt`) — the cost
  / benefit doesn't pencil out.
- No new e2e tests. The defect classes this change targets are
  better caught at the layer where the defect lives.

## Decisions

### 1. Hypothesis over manual parametrize for value objects

Decision: every domain value object gets one property test in
place of (not in addition to) further hand-written parametrize
cases. The existing parametrize cases are kept because they
double as documentation of expected boundary behaviour.

Rationale: a parametrize block stops finding bugs the moment
the contributor stops adding cases. A `@given` block keeps
searching every CI run. The cost is ~100 ms per property at
default `max_examples=100`; the benefit is shrinking
counter-examples that pinpoint the minimal failing input.

### 2. Schema-vs-ORM check uses `information_schema`, not `inspect()`

Decision: the consistency test queries
`information_schema.columns` (and `pg_constraint` where needed)
directly, instead of asking SQLAlchemy `Inspector` to introspect
the DB and diff against `Base.metadata`. The diff is computed in
Python.

Rationale: `Inspector` normalises types (e.g. `citext` → `TEXT`,
`uuid` → `UUID(as_uuid=True)`) so genuine type mismatches are
invisible. Reading the raw catalog row preserves Postgres-side
truth. The diff is small (table, column, nullability, data_type
family) and explicit — when it fires, the failure message
names the column and side that disagrees.

### 3. RLS test connects as `nica_erp_app`, not as superuser

Decision: the new
`test_rls_policy_enforcement.py` opens its session against the
`database_url` fixture (which authenticates as `nica_erp_app`),
not against a fresh superuser engine. Seed data is inserted
once through the superuser-bypass path the conftest's
`_run_migrations` already authorises; query-side proves the
posture under app credentials.

Rationale: the *whole point* is that the policy must be
enforced against the role production runs as. Connecting as
the superuser inverts the test — it would pass even if RLS
were disabled. The conftest already separates the two roles
exactly for this reason, and the test consumes that separation
instead of re-establishing it.

### 4. `_factories/` lives under `tests/`, exported as a package

Decision: the factory module is `apps/api/tests/_factories/`.
The leading underscore signals "test infrastructure, not
production code"; the `tests` parent keeps the factory out of
`pythonpath` for production imports while remaining importable
from any test file via `from tests._factories.identity import
make_password`.

Rationale: the alternative — putting factories under
`src/contexts/<x>/testing.py` — would require every factory to
respect the import-linter contracts that gate productive code,
which they shouldn't (e.g. a factory may want to construct an
aggregate in an invalid state to exercise a guard). The
`tests/_factories/` location is already covered by the mypy
`tests.*` override.

### 5. Triad lanes are additive, not replacement

Decision: `make test-be-unit`, `make test-be-integration`,
and `make test-be-e2e` are added alongside the existing
`test-api`, `test-be-coverage`, `test-all`. CI is unchanged —
it still runs the full suite via the existing recipes.

Rationale: the lanes are a developer-ergonomics affordance, not
a CI optimisation. Splitting CI lanes would force two more
testcontainer boots per push and save nothing. Keeping them as
local-only is the cheap win.

## Risks / Trade-offs

- **Hypothesis flakes on a slow CI runner.** Default
  `deadline=200ms` can trip on cold CI agents. Mitigation: set
  `settings.register_profile("ci", deadline=None,
  max_examples=200)` in `apps/api/conftest.py` and load it via
  `HYPOTHESIS_PROFILE` env var in the CI workflow. Local runs
  use the default profile.
- **Schema-vs-ORM check fires on legitimate migrations
  in-flight.** A contributor adding a column in a migration
  has to add the matching mapper attribute in the same PR.
  This is the *intended* friction; it is the difference between
  catching drift on day one vs day thirty. Mitigation: the
  test's failure message points at the missing mapper
  attribute by name, so the fix is mechanical.
- **RLS-policy test is timing-sensitive in CI.** The
  `set_config('app.tenant_id', …)` call uses
  `current_setting('app.tenant_id', true)` inside the policy
  body; both are session-scoped. Mitigation: the test opens a
  dedicated `AsyncSession` per assertion, never reuses, and
  explicitly resets the setting in a `finally` block.
- **`_factories/` becomes a dumping ground.** Future
  contributors may add unrelated helpers there. Mitigation:
  the spec restricts the package to "canonical domain object
  builders + DB row seeders"; anything else belongs to a
  per-context `tests/<layer>/contexts/<x>/_support.py`.
