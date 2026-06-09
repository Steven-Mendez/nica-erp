# Migrate persistence adapters to SQLAlchemy Core statements

## Why

Every persistence adapter builds SQL as raw strings passed to `text()`. The pattern is safe today, but only through hand-maintained guardrails: `ORDER BY` whitelists, conditional `bindparam(expanding=True)` declarations, f-string interpolation of `_COLUMNS` constants, per-call `nosemgrep` suppressions, and a per-directory ruff E501 carve-out. Each new query re-pays that tax and re-creates the same injection-review surface. SQLAlchemy Core `Table` metadata + the statement builder removes the string assembly entirely while preserving every guarantee the current design was chosen for: no ORM instrumentation, pure domain objects, exactly one statement per `execute()`, RLS via session GUCs, and the `assert_query_count` N+1 gate.

## What Changes

- Add SQLAlchemy Core `Table` metadata modules (imperative `Table(...)` definitions, no `DeclarativeBase`) for the business tables each adapter touches: `tenants`, `tenant_members`, `invitations`, `users`, `auth_local_users`, `auth_local_refresh_tokens`, `outbox`, `role_permissions`.
- Rewrite the statement construction in the seven `text()`-based adapters to Core builder expressions (`select()`/`insert()`/`update()`), keeping ports, method signatures, and manual hydration to domain objects unchanged:
  - `shared_kernel/adapters/outbox_sqlalchemy.py`
  - `contexts/identity/.../sqlalchemy/user_repository.py`
  - `contexts/identity/.../sqlalchemy/auth_local_users.py`
  - `contexts/identity/.../sqlalchemy/auth_local_refresh_tokens.py`
  - `contexts/tenants/.../sqlalchemy/tenant_repository.py`
  - `contexts/tenants/.../sqlalchemy/membership_repository.py`
  - `contexts/tenants/.../sqlalchemy/invitation_repository.py`
- Migrate the two remaining business-table `text()` lookups outside repositories: the membership check in `contexts/tenants/adapters/inbound/http/middleware.py` and the `role_permissions` lookup in `bootstrap/dependencies.py`.
- Replace string-based dynamic query mechanics in `membership_repository.list_page`: the `WHERE` builder becomes composed column expressions, the `ORDER BY` whitelist maps to `Column` objects, `IN` filters use `.in_()` (no conditional `bindparam(expanding=True)`).
- Remove the now-unneeded `nosemgrep: avoid-sqlalchemy-text` suppressions and the ruff E501 per-directory ignore for the tenants persistence adapters.
- Add a schema-consistency integration test asserting the Core metadata matches the Alembic-managed database schema (columns and types per table).
- Out of scope / unchanged: RLS `SET LOCAL` GUC statements (`bootstrap/container.py`, use cases), `/healthz` probes (`SELECT 1`, `alembic_version`), Alembic hand-written migrations (`target_metadata` stays `None`; `--autogenerate` stays off), all domain and application code, all test seed helpers.

Not **BREAKING**: emitted SQL is semantically equivalent; ports and HTTP behavior are unchanged.

## Capabilities

### New Capabilities

- `persistence-core-statements`: persistence adapters build business-table statements from shared Core `Table` metadata via the SQLAlchemy statement builder — no raw SQL strings, no ORM mapping, domain hydration stays manual, and the metadata is verified against the migrated schema.

### Modified Capabilities

<!-- none: repository behavior, UoW semantics, outbox semantics, and RLS requirements are unchanged; this swaps statement construction, an implementation detail below existing spec requirements -->

## Impact

- **Code**: the seven adapter files above, plus new `tables.py` metadata modules under `shared_kernel/adapters/` and each context's `adapters/outbound/persistence/sqlalchemy/`; `middleware.py` and `bootstrap/dependencies.py` lookups.
- **Tests**: existing integration tests under `apps/api/tests/integration/` must pass unchanged (including `assert_query_count` gates); one new metadata↔schema consistency test.
- **Lint/security tooling**: deletes all `avoid-sqlalchemy-text` suppressions in adapters; drops the tenants-persistence E501 ignore from `pyproject.toml`.
- **Dependencies**: none added — SQLAlchemy 2.0 async is already in place; only the unused-by-design ORM layer remains unused.
- **Docs**: new ADR recording the statement-builder decision as a refinement of ADR-0010; sprint doc follow-up entry.
