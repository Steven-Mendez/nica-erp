# ADR-0036 — SQLAlchemy Core statement builder over text() raw SQL

**Status**: Accepted
**Date**: 2026-06-09

## Context

[ADR-0010](0010-python-fastapi.md) chose SQLAlchemy 2.0 async with imperative mapping, rejecting Active Record ORMs to keep the domain pure ([ADR-0001](0001-hexagonal-architecture.md)). The implementation landed on raw SQL strings wrapped in `text()`, which forces hand-maintained guardrails on every dynamic query: `ORDER BY` whitelist dicts, conditional `bindparam(expanding=True)`, f-string interpolation of column-list constants, per-call `nosemgrep` suppressions, and a ruff E501 carve-out. Each new query re-pays that tax and re-creates an injection-review surface.

## Decision

Persistence adapters build business-table statements with the SQLAlchemy Core statement builder (`select()`/`insert()`/`update()`) over imperative `Table` metadata attached to a single shared `MetaData` in the shared kernel. Tables created by shared-kernel migrations (`users`, `tenants`, `outbox`, `role_permissions`) are defined there; context-owned tables live in their context's persistence package, and contexts never import metadata from another context. Domain hydration stays manual; no declarative base, no `map_imperatively()`. Alembic keeps hand-written revisions (`target_metadata = None`, no autogenerate); an integration test compares the metadata against the migrated schema and fails on drift. `text()` remains only for RLS `set_config` GUCs, `/healthz` probes, and test utilities.

## Consequences

- (+) Dynamic queries compose column expressions instead of strings: no whitelist interpolation, no expanding-bindparam bookkeeping, no `nosemgrep` suppressions, no E501 carve-out.
- (+) All guarantees of the previous design hold: pure domain objects, exactly one statement per `execute()` (RLS [ADR-0002](0002-postgres-rls.md) and the `assert_query_count` gate), unchanged ports.
- (+) JSONB/citext typing in metadata removes `CAST(... AS jsonb)` workarounds; adapters pass dicts.
- (−) The schema now exists in two representations (migrations + metadata); mitigated by the consistency test — previously the duplication (`_COLUMNS` constants) was unchecked.
- (−) Emitted SQL is one step removed from the source; reviewers read builder expressions instead of literal SQL. Statement constants stay at module top for visibility.

## Alternatives

- **Keep `text()` raw SQL** — rejected: the guardrail tax grows with every dynamic query; the members-list pagination already needed whitelist dicts, conditional expanding binds, and six suppressions in one file.
- **Imperative ORM mapping (`map_imperatively`)** — rejected: runtime instrumentation reintroduces dirty tracking, autoflush, and lazy-load hazards (the `expire_on_commit` sharp edges [ADR-0010](0010-python-fastapi.md) accepted as a known cost); domain object behavior would depend on session attachment.
- **aiosql / SQL files** — rejected: bypasses the `AsyncSession`, breaking the Unit of Work, RLS GUC injection ([ADR-0002](0002-postgres-rls.md)), and the transactional outbox ([ADR-0006](0006-transactional-outbox.md)).
- **Declarative ORM / SQLModel** — rejected: same dependency-rule violation as Tortoise/Prisma in [ADR-0010](0010-python-fastapi.md).

## Revisit triggers

- The consistency test produces chronic false positives on type comparison and starts getting scoped down — reconsider reflection-based checking or autogenerate adoption.
- A future capability needs statement features Core expresses poorly (e.g. heavy CTE/window composition) and teams reach for `text()` again — revisit the boundary between builder and raw SQL.

Detail in [`../02-architecture.md`](../02-architecture.md).
