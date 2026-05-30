## Why

The in-flight `test-backfill-and-e2e-tooling` change raises
*coverage* numbers but coverage is not the same as
*defect-finding power*. Three classes of real bugs slip past the
current backend triad:

1. **Invariant edge cases.** The `Ruc`, `Password`,
   `Municipality`, and `Regime` value objects are exercised by
   five or six hand-picked strings each. Adversarial input
   (unicode confusables, leading whitespace inside the body,
   13-digit RUCs that happen to satisfy the regex but break
   downstream lookups, 8-char passwords missing a single class)
   is not searched. A reviewer who adds a regex tweak today gets
   a green build even when half of the input space silently
   becomes invalid.
2. **Schema / ORM drift.** Alembic migrations and SQLAlchemy
   models are authored separately. Nothing in CI fails when a
   migration adds a column that no ORM model maps, or when a
   model declares a column the latest migration never created.
   The first symptom is an integration test that mysteriously
   returns `None` for a freshly written value, or a production
   `UndefinedColumn` error.
3. **RLS posture.** The existing
   `test_rls_tenant_isolation.py` proves that the *HTTP layer*
   honours the tenant claim, but it does not prove the
   *Postgres policy* itself rejects a forged
   `app.tenant_id`. If a future migration drops `FORCE ROW LEVEL
   SECURITY` or marks `nica_erp_app` as `BYPASSRLS`, every HTTP
   test still passes — the safety net is woven from a single
   strand.

This change keeps the existing triad (no new layers, no
mutation testing, no fuzzing) but **adds tests that look for
real defects** at the layer where each defect actually lives:

- **Unit (property-based).** `hypothesis` searches the input
  space of every domain value object so the regex itself is
  what's under test, not the five strings a human thought of.
- **Integration.** A schema-vs-ORM consistency check runs after
  `alembic upgrade head` and asserts that every mapped table
  and column exists in `information_schema`, and vice versa for
  every public table the policy migrations gate.
- **Integration.** A direct RLS-policy test connects as
  `nica_erp_app` (the NOBYPASSRLS app role the conftest
  provisions), sets `app.tenant_id` to tenant B, and asserts
  zero tenant-A rows are visible — even via raw `SELECT`, even
  with the HTTP middleware absent.

The change also lays one piece of test infrastructure that the
in-flight backfill keeps re-inventing: shared `_factories/`
helpers that build canonical-shape domain objects and seed rows.
Three existing tests are refactored to use them as worked
examples; the rest are left to future PRs.

Finally, three Makefile recipes (`test-be-unit`,
`test-be-integration`, `test-be-e2e`) expose the triad lanes
explicitly so contributors can run the cheapest layer first and
the slowest layer last, instead of paying the testcontainer
boot cost for a one-line value-object change.

## What Changes

### Backend test dependencies

- Add `hypothesis>=6,<7` to `apps/api/pyproject.toml`
  `[dependency-groups].dev`. No production dependency added.

### Backend unit tests — coverage of unguarded use cases

- `tests/unit/contexts/tenants/application/test_list_members.py`
  — happy-path returns the repository's list verbatim and runs
  under the UoW. (The use case is a pass-through but it is
  *exposed* by `GET /v1/tenants/{tenant_id}/members`; if the
  signature drifts the route silently returns 500.)
- `tests/unit/contexts/tenants/application/test_list_invitations.py`
  — same shape for `ListInvitations`.

### Backend unit tests — property-based invariants

- `tests/unit/contexts/identity/domain/test_password_properties.py`
  — three properties:
  - any string that satisfies the policy survives a round-trip;
  - any string shorter than 8 chars OR missing a class raises
    `PasswordPolicyError`;
  - `repr(Password(secret))` never contains the plaintext.
- `tests/unit/contexts/tenants/domain/test_value_object_properties.py`
  — properties for:
  - `Ruc.parse` accepts every string matching
    `\d{13}[A-Z]` (with surrounding whitespace) and rejects
    every string that does not;
  - `Municipality(v)` accepts exactly the names in
    `KNOWN_MUNICIPALITIES` (no false positives, no false
    negatives);
  - `Regime(v)` accepts only `{"general", "simplified"}`.

### Backend integration tests — real-defect guards

- `tests/integration/shared_kernel/test_schema_consistency.py`
  — after the session-scoped `_run_migrations` fixture has run,
  query `information_schema.columns` for the `public` schema
  and assert that every column declared on a SQLAlchemy mapper
  also exists in the database, with the same nullability. The
  test names the diff if it fails. This is the migration-drift
  guard.
- `tests/integration/contexts/tenants/test_rls_policy_enforcement.py`
  — open a session as `nica_erp_app`, seed two tenants with one
  row each (via a superuser session bypassing RLS), then set
  `app.tenant_id` to tenant B and assert `SELECT … FROM
  tenant_members` returns exactly tenant B's row and never
  tenant A's. Repeat for `invitations`. This is the RLS
  posture guard.

### Backend test infrastructure — factories

- Add `apps/api/tests/_factories/__init__.py`,
  `_factories/identity.py`, `_factories/tenants.py` with:
  - `make_password(value="Demo1234!@xy") -> Password`
  - `make_user(...) -> User` (identity aggregate)
  - `make_tenant(...) -> Tenant` (tenants aggregate)
  - `seed_tenant_row(session, ...) -> uuid.UUID`
  - `seed_membership_row(session, ..., role="owner") -> None`
- Refactor three existing tests to consume the factories as
  worked examples (kept narrow — bulk migration is future work).

### Triad-respecting Makefile lanes

- `make test-be-unit` — `cd apps/api && uv run pytest tests/unit`.
- `make test-be-integration` —
  `cd apps/api && uv run pytest tests/integration`.
- `make test-be-e2e` — `cd apps/api && uv run pytest tests/e2e`.
- The existing `test-api`, `test-be-coverage`, and `test-all`
  recipes keep their current behaviour.

### Out of scope

- No production code changes.
- No new bounded context.
- No mutation testing (`mutmut`), no fuzzing
  (`atheris`), no schemathesis. Those belong to a later change
  if the property-based layer turns out to leave defects on
  the floor.
- No frontend test changes — this change is backend-only.
- No coverage threshold change — the 89/90 % gate is owned by
  `test-backfill-and-e2e-tooling`.

## Impact

- Affected specs: `backend-test-quality-guards` (new).
- Affected code:
  - `apps/api/pyproject.toml` (one dev dep added).
  - `apps/api/tests/unit/contexts/identity/domain/`
    (one new file).
  - `apps/api/tests/unit/contexts/tenants/application/`
    (two new files — `test_list_members.py`,
    `test_list_invitations.py`).
  - `apps/api/tests/unit/contexts/tenants/domain/`
    (one new file).
  - `apps/api/tests/integration/shared_kernel/`
    (one new file).
  - `apps/api/tests/integration/contexts/tenants/`
    (one new file).
  - `apps/api/tests/_factories/` (new).
  - Three existing test files (refactored to use factories).
  - `Makefile` (three new recipes).
- Affected docs: none. The triad guidance already lives in
  `docs/04-testing-strategy.md`; the spec under
  `openspec/specs/backend-test-quality-guards/` is the
  durable home for the property-test policy.
