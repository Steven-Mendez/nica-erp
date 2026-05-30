## 1. Test dependencies

- [x] 1.1 Add `hypothesis>=6,<7` to `apps/api/pyproject.toml`
      `[dependency-groups].dev`. Run `uv lock` so
      `uv.lock` reflects the new dep.
- [x] 1.2 Register a `ci` Hypothesis profile in
      `apps/api/conftest.py` (deadline `None`,
      `max_examples=200`) and a `dev` profile (defaults). Load
      via `HYPOTHESIS_PROFILE` env var; default to `dev` so
      local runs stay snappy.

## 2. Unit tests — close gaps in use-case coverage

- [x] 2.1 `tests/unit/contexts/tenants/application/test_list_members.py`
      — assert the use case opens the UoW and returns the
      repository's `list_by_tenant` result verbatim.
- [x] 2.2 `tests/unit/contexts/tenants/application/test_list_invitations.py`
      — same shape for `ListInvitations`.

## 3. Unit tests — property-based domain invariants

- [x] 3.1 `tests/unit/contexts/identity/domain/test_password_properties.py`
      — three properties:
      - any `Password` constructed from a policy-satisfying
        string survives `validate_policy()`;
      - any string under 8 chars OR missing a required class
        raises `PasswordPolicyError`;
      - `repr(Password(s))` is always the masked literal,
        regardless of `s`. (Tightened from the original
        "`s not in repr(...)`" because the masked literal
        itself contains `*`; Hypothesis found `s='*'` as the
        minimal counter-example — the constant-equality
        assertion is the true invariant.)
- [x] 3.2 `tests/unit/contexts/tenants/domain/test_value_object_properties.py`
      — properties for `Ruc`, `Municipality`, `Regime`:
      - `Ruc.parse(s)` succeeds iff `s.strip()` matches
        `\d{13}[A-Z]`;
      - `Municipality(s)` succeeds iff `s in KNOWN_MUNICIPALITIES`;
      - `Regime(s)` succeeds iff `s in {"general",
        "simplified"}`.

## 4. Integration tests — schema-vs-repository consistency

- [x] 4.1 `tests/integration/shared_kernel/test_schema_consistency.py`
      — after the session-scoped `_run_migrations` fixture, query
      `information_schema.columns` and assert every column
      referenced by each repository's `_COLUMNS` constant exists
      in the corresponding table. Scope pivot from the original
      "ORM-vs-DB" plan: the codebase uses raw SQL via
      `text()`, not ORM mappers, so the guard is rooted on the
      ``_COLUMNS`` constants in
      `contexts/*/adapters/outbound/persistence/sqlalchemy/*.py`
      plus an explicit list for the inline-SQL `users` table.

## 5. Integration tests — RLS policy enforcement

- [x] 5.1 `tests/integration/contexts/tenants/test_rls_policy_enforcement.py`
      — seed tenants A and B with one membership each, then open
      an `AsyncSession` as `nica_erp_app`, set `app.tenant_id` to
      B's id, `SELECT id FROM tenant_members`, and assert exactly
      tenant B's row is returned. Repeat for tenant A. Repeat the
      matrix for `invitations`. Verify the zero-UUID sentinel
      hides everything. Verify `nica_erp_app` is NOBYPASSRLS.
      Scope refinement: the original "unset GUC" assertion
      crashed on `''::uuid`; production uses the zero-UUID
      sentinel via `bootstrap/container.py._ZERO_UUID` and that
      is now the asserted state.

## 6. Test infrastructure — factories

- [x] 6.1 `apps/api/tests/_factories/__init__.py` — empty
      package marker.
- [x] 6.2 `apps/api/tests/_factories/identity.py` — exports
      `make_password(value="Demo1234!@xy") -> Password`,
      `make_user(*, external_sub=..., email=..., now=...) -> User`.
- [x] 6.3 `apps/api/tests/_factories/tenants.py` — exports
      `make_tenant`, `make_membership`, `make_invitation`,
      `seed_tenant_row`, `seed_user_row`,
      `seed_membership_row`, `seed_invitation_row`. The seed
      helpers set `app.tenant_id` before INSERT so the RLS
      `WITH CHECK` policy passes under `nica_erp_app`.
- [x] 6.4 Worked-example consumption: the two new use-case unit
      tests (`test_list_members.py`, `test_list_invitations.py`)
      consume `make_membership` / `make_invitation`; the new
      integration RLS test consumes every `seed_*_row` helper.
      Bulk refactoring of pre-existing tests is deferred to
      future PRs to keep this change's diff focused on the new
      guards.

## 7. Makefile lanes

- [x] 7.1 `make test-be-unit` — `cd apps/api && uv run pytest
      tests/unit`.
- [x] 7.2 `make test-be-integration` — `cd apps/api && uv run
      pytest tests/integration`.
- [x] 7.3 `make test-be-e2e` — `cd apps/api && uv run pytest
      tests/e2e`.
- [x] 7.4 `make help` now lists each new recipe (also tightened
      the awk pattern from `[a-zA-Z_-]+` to `[a-zA-Z0-9_-]+` so
      `test-be-e2e` itself shows up — the original pattern
      excluded targets containing digits).

## 8. Closure

- [x] 8.1 `make test-be-unit` green: 186 tests, 6.91 s.
- [x] 8.2 `make test-be-integration` green: 89 tests, 6.97 s.
- [x] 8.3 `make test-be-e2e` green: 10 tests, 6.74 s.
- [x] 8.4 `make test-api` green: 285 tests, 12.68 s.
- [x] 8.5 `ruff check`, `mypy --strict`, and `lint-imports`
      green on every new file.
- [x] 8.6 Archive: move the change directory to
      `openspec/changes/archive/2026-05-29-add-backend-test-quality-guards/`.
