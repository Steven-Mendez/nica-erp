# Tasks — migrate persistence to SQLAlchemy Core statements

## 1. Documentation first

- [x] 1.1 Add a follow-up entry to the current sprint doc (`docs/sprints/`) describing the Core statement-builder migration as a mini-change (no openspec references, per doc hierarchy)
- [x] 1.2 Write the new ADR (next free number; 0036 at proposal time) "SQLAlchemy Core statement builder over text() raw SQL", refining ADR-0010: context, decision, alternatives already evaluated (keep `text()`, `map_imperatively`, aiosql), consequences, revisit triggers; link it from `docs/adr/README.md` if an index exists

## 2. Table metadata + consistency gate

- [x] 2.1 Create `apps/api/src/shared_kernel/adapters/tables.py` with the shared `MetaData` and `Table` definitions for `users`, `tenants`, `outbox`, `role_permissions` (JSONB columns as `postgresql.JSONB`, emails as `CITEXT`), mirroring Alembic migrations 0001/0002/0003/0004/0006
- [x] 2.2 Create `apps/api/src/contexts/identity/adapters/outbound/persistence/sqlalchemy/tables.py` with `auth_local_users` and `auth_local_refresh_tokens` (migrations 0002/0007) on the shared `MetaData`
- [x] 2.3 Create `apps/api/src/contexts/tenants/adapters/outbound/persistence/sqlalchemy/tables.py` with `tenant_members` and `invitations` (migrations 0003/0005/0008) on the shared `MetaData`
- [x] 2.4 Add the schema-consistency integration test under `apps/api/tests/integration/shared_kernel/` using `alembic.autogenerate.compare_metadata` against the migrated test database, scoped with `include_object` to modeled tables; assert zero drift (design D6, including documented reflection fallback if needed) — replaced the prior `_COLUMNS`-string guard in `test_schema_consistency.py`, which this supersedes

## 3. Migrate adapters (one per task, integration tests green after each)

- [x] 3.1 `contexts/identity/.../sqlalchemy/auth_local_refresh_tokens.py` — INSERT/UPDATE/SELECT to builder statements (WHERE bindparam renamed `b_jti`; two call sites in `local.py` updated)
- [x] 3.2 `shared_kernel/adapters/outbox_sqlalchemy.py` — INSERT to builder; drop `CAST(... AS jsonb)` by passing the payload dict through the JSONB column type
- [x] 3.3 `contexts/identity/.../sqlalchemy/user_repository.py` — SELECTs (including `get_by_ids` via `.in_()`, deleting the expanding bindparam), INSERT, UPDATE; JSONB `preferences` as dict
- [x] 3.4 `contexts/tenants/.../sqlalchemy/invitation_repository.py` — SELECTs (case-insensitive email via `func.lower`), INSERT, UPDATE
- [x] 3.5 `contexts/tenants/.../sqlalchemy/tenant_repository.py` — SELECTs (including the `tenant_members` subquery), INSERT, UPDATE; keep IntegrityError mapping for RUC uniqueness
- [x] 3.6 `contexts/identity/.../sqlalchemy/auth_local_users.py` — all eight statements; `UPDATE_ACTIVE_TENANT` via `func.jsonb_set`; `attributes` as dict through JSONB type (UPDATE call sites in `local.py` now pass `b_id`)
- [x] 3.7 `contexts/tenants/.../sqlalchemy/membership_repository.py` — static statements plus `list_page`: WHERE as composed expressions, `_SORT_COLUMNS` mapping to `Column` objects, `.in_()` filters, `func.lower(...).like(needle, escape="\\")` search, shared WHERE between page and COUNT; delete `_build_filter` string assembly and `_expanding_binds`

## 4. Remaining business-table lookups

- [x] 4.1 `contexts/tenants/adapters/inbound/http/middleware.py` — membership check via `tenant_members` metadata
- [x] 4.2 `bootstrap/dependencies.py` — `role_permissions` lookup via shared-kernel metadata (plus the `tenant_members` active-role lookup in `current_actor`, same pattern)

## 5. Cleanup and verification

- [x] 5.1 Remove all `nosemgrep: avoid-sqlalchemy-text` suppressions from adapter files and the tenants-persistence E501 per-directory ignore in `apps/api/pyproject.toml`
- [x] 5.2 Audit: remaining `text(` under `apps/api/src` is only `set_config` GUCs (`bootstrap/container.py`, create_tenant/accept_invitation use cases) and `/healthz` probes (spec scenario "Adapter sources contain no business-table text() statements")
- [x] 5.3 Run the full `apps/api` test suite (unit + integration, including `assert_query_count` gates) and lint/mypy; everything green with no test modifications other than the new consistency test — 420 passed (unit+integration+e2e), `ruff check`/`format` clean, `mypy --strict` clean
