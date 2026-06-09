# Design — migrate persistence to SQLAlchemy Core statements

## Context

ADR-0010 chose SQLAlchemy 2.0 async with imperative mapping and Unit of Work, explicitly rejecting Active Record ORMs. The implementation landed on the most austere point of that spectrum: every adapter assembles SQL strings and wraps them in `text()`. No `Table` metadata exists anywhere (`alembic/env.py` runs with `target_metadata = None`), so dynamic queries (`membership_repository.list_page`) require string-assembly guardrails: `ORDER BY` whitelist dicts, conditional `bindparam(expanding=True)`, LIKE escaping, per-call `nosemgrep` suppressions, and a ruff E501 carve-out for the tenants persistence directory.

Constraints that must survive the migration:

- Domain stays pure: no instrumentation, no declarative models, manual hydration (`*.hydrate(...)`) unchanged (ADR-0001, ADR-0010).
- Exactly one statement per `execute()`: RLS GUC discipline (ADR-0002) and the `assert_query_count` N+1 gate depend on it.
- Ports and method signatures unchanged; this is adapter-internal.
- Alembic migrations remain hand-written; `--autogenerate` stays off.

## Goals / Non-Goals

**Goals:**

- Replace string assembly with Core `Table` metadata + statement builder in all business-table adapters.
- Eliminate the string-safety guardrails (whitelist interpolation, expanding bindparams, `nosemgrep`, E501 ignore) that exist only because SQL is built from strings.
- Pin metadata to the real schema with an automated consistency check.

**Non-Goals:**

- No ORM adoption: no `DeclarativeBase`, no `map_imperatively()`, no sessions tracking domain objects.
- No behavior, port, or HTTP contract changes; no new endpoints or capabilities visible to callers.
- No Alembic workflow change (`target_metadata` stays `None` in `env.py`; migrations stay hand-written).
- No migration of RLS `SET LOCAL set_config(...)` statements, `/healthz` probes, or test seed helpers — `text()` remains correct there.

## Decisions

**D1 — Core `Table` metadata, one definition per table, attached to a single shared `MetaData`.**
A module-level `MetaData()` lives in `shared_kernel/adapters/tables.py`. Each table is defined exactly once with `Table(...)` (imperative form). Rationale: one registry enables the schema-consistency test to iterate every modeled table; imperative `Table` is pure metadata with zero instrumentation. Alternative rejected: per-adapter ad-hoc `table()`/`column()` lightweight constructs — they skip types (losing JSONB/`citext` handling) and can't be schema-checked.

**D2 — Table placement follows the migration that owns the table.**
- `shared_kernel/adapters/tables.py`: `users`, `tenants` (created by shared-kernel migration 0001), `outbox`, `role_permissions` (RBAC catalog already lives in `shared_kernel/permissions/`).
- `contexts/identity/.../persistence/sqlalchemy/tables.py`: `auth_local_users`, `auth_local_refresh_tokens`.
- `contexts/tenants/.../persistence/sqlalchemy/tables.py`: `tenant_members`, `invitations`.

Rationale: `membership_repository` joins `tenant_members` with `users`, and `tenant_repository`/`bootstrap/dependencies.py` read `tenants`/`role_permissions`; placing the shared tables in the shared kernel lets both contexts import them without cross-context imports. Alternative rejected: defining `users` in identity and importing it from tenants — violates context isolation.

**D3 — Statements stay precompiled as module constants where they are static.**
Today's `_SELECT_*`/`_INSERT`/`_UPDATE` constants become `select(...)`/`insert(...)`/`update(...)` expressions at module level; only `list_page` builds statements per call. Rationale: keeps the current "the query is visible at the top of the file" reviewability and avoids per-request construction cost for the common path.

**D4 — `list_page` dynamics become expression composition.**
- WHERE: a `list[ColumnElement[bool]]` combined with `and_()`; the search clause uses `func.lower(col).like(needle, escape="\\")` with the existing Python-side escaping of `%`/`_`/`\` (behavior identical to today's `ESCAPE '\\'`).
- IN filters: `tm.c.role.in_([...])` — SQLAlchemy handles expansion; the conditional `_expanding_binds` helper is deleted.
- ORDER BY: `_SORT_COLUMNS` maps sort keys to `Column` objects and `_SORT_DIRECTIONS` to `asc`/`desc` wrappers — same whitelist semantics, but a wrong key now fails type-visibly instead of being a string-interpolation hazard.
- COUNT: `select(func.count()).select_from(...)` sharing the same WHERE list as the page query.

**D5 — JSONB columns typed as `postgresql.JSONB` in metadata; adapters pass dicts.**
Removes the `CAST(:payload AS jsonb)` / `CAST(:attributes AS jsonb)` workarounds — the column type serializes. The `auth_local_users.UPDATE_ACTIVE_TENANT` JSONB mutation becomes `func.jsonb_set(...)` with bound values. `email` columns use `sqlalchemy.dialects.postgresql.CITEXT`.

**D6 — Schema-consistency integration test via Alembic `compare_metadata`.**
A new integration test runs migrations (existing test infra), builds a `MigrationContext` from the live connection, and asserts `alembic.autogenerate.compare_metadata(ctx, metadata)` returns no diffs, filtered with `include_object` to the modeled tables and with server-default/index comparison tuned to what the metadata intentionally models. Rationale: catches drift in both directions (future migration not reflected in metadata, or metadata inventing columns) without enabling autogenerate in `env.py`. Fallback if `compare_metadata` proves too strict on type rendering: reflect with `MetaData.reflect` and compare column names + type affinities.

**D7 — Docs: new ADR refining ADR-0010; sprint follow-up entry.**
A new ADR (next free number, 0036 at time of writing) records "SQLAlchemy Core statement builder over `text()` raw SQL" as a refinement of ADR-0010 — ADR-0010 stays Accepted (the stack is unchanged); the new ADR captures alternatives already evaluated (keep `text()`, `map_imperatively`, aiosql) and revisit triggers. The current sprint doc gets a follow-up entry per the established mini-change convention.

**D8 — The semgrep `avoid-sqlalchemy-text` rule keeps its value.**
After migration, remaining `text()` calls are only GUC `set_config`, health probes, and test seeds; all adapter suppressions are deleted, so any future `text()` in an adapter surfaces as a clean semgrep finding instead of drowning among 15 suppressed ones.

## Risks / Trade-offs

- [Semantic drift in rewritten queries (NULL handling, ordering ties, LIKE escaping)] → migrate one adapter per task with the full integration suite green after each; `assert_query_count` gates already pin statement counts; the membership search tests cover the `%`/`_` escaping behavior explicitly.
- [JSONB value passing changes (dict vs pre-serialized string)] → existing round-trip integration tests (`preferences`, `attributes`, outbox `payload`) are the gate; adjust adapters, not tests.
- [Metadata drifts from future hand-written migrations] → D6 consistency test fails the suite locally before merge (no CI by ADR-0023, so this is the enforcement point).
- [Two representations of the schema (migrations + metadata)] → accepted; today's `_COLUMNS` constants already duplicate column lists per adapter, and D6 makes the new duplication checked instead of unchecked.
- [`compare_metadata` over-reports on defaults/constraints we don't model] → scope comparison via `include_object`; documented fallback to reflection-based comparison in D6.

## Migration Plan

1. Docs first (sprint follow-up entry, new ADR), per the project's documentation flow.
2. Land `tables.py` metadata modules + consistency test (test proves metadata matches schema before any adapter changes).
3. Migrate adapters one per commit, simplest first (`auth_local_refresh_tokens` → `outbox` → `user_repository` → `invitation_repository` → `tenant_repository` → `auth_local_users` → `membership_repository`), running `apps/api` integration tests after each.
4. Migrate `middleware.py` and `bootstrap/dependencies.py` lookups.
5. Cleanup: remove `nosemgrep` suppressions and the E501 per-directory ignore; full suite + lint.

No deploy choreography: the API image rebuilds on next `make deploy`; no schema changes ship. Rollback = revert the commits (ports unchanged, so partial rollback per adapter is safe).

## Open Questions

- None blocking. If `CITEXT` typing causes friction with the test container image, fall back to `TEXT` in metadata with the consistency test's type comparison relaxed for those columns (the database column remains `citext` via migrations either way).
