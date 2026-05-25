# ADR-0028 — Data migration strategy

**Status**: Provisional — patterns canonized without having written a non-trivial migration. No sprint 00-09 references this ADR. Revisit after sprint 04 (first multi-table migration with backfill) so the recipe is validated against real friction.
**Date**: 2026-05-23

## Context
Several ADRs imply data transformations: [ADR-0013](0013-utc-everywhere.md) (UTC-everywhere), [ADR-0014](0014-soft-delete.md) (soft-delete columns), [ADR-0011](0011-uuidv7-identifiers.md) (UUIDv7 PKs), and any future schema change. [ADR-0010](0010-python-fastapi.md) picks Alembic but doesn't say how migrations should be **shaped** to survive rolling deploys ([ADR-0018](0018-rolling-deploys.md)) without downtime once the first tenant is live. Without a policy, the first non-trivial migration becomes a 30-minute outage.

## Decision
**Expand → migrate data → contract. Every migration is two deploys when contracting is involved. Within a deploy, every migration is forward-compatible with the previous version of the code.**

### Migration shapes

| Shape | Sequence | Example |
|---|---|---|
| **Additive** | one migration | Add a nullable column, add an index `CONCURRENTLY`, add a table |
| **Backfill** | migration adds column nullable → app dual-writes → backfill script populates → migration sets `NOT NULL` | Add `tenant_timezone` to `tenants` |
| **Rename** (two deploys) | (1) add new column, app writes both, reads new; (2) drop old column | Rename `customer.name` → `customer.legal_name` |
| **Type change** (two deploys) | (1) add `<col>_v2` with new type, dual-write, backfill; (2) drop old, rename | `created_at TIMESTAMP` → `created_at TIMESTAMPTZ` |
| **Destructive** (catalog only) | direct DROP allowed only on catalog tables behind soft-delete ([ADR-0014](0014-soft-delete.md)); never on fiscal data | Drop a deactivated product category table |

### Rules
- **Fiscal tables are append-only** ([ADR-0014](0014-soft-delete.md)). Migrations may add columns but never rewrite rows. Historical data preserved verbatim for DGI audit.
- **`CREATE INDEX` always uses `CONCURRENTLY`** outside transactions. Alembic supports this via `op.execute("CREATE INDEX CONCURRENTLY ...")` + `transactional_ddl = False` in env.py.
- **`ALTER TABLE ... SET NOT NULL` runs only after backfill is verified** by a SELECT count.
- **Long backfills run as one-off ECS tasks**, not as Alembic upgrades. Alembic flips the constraint at the end. Pattern: `make backfill SCRIPT=backfill_tenant_timezone`.
- **Every migration is reversible** (`downgrade()` is real, not `pass`), unless explicitly marked `irreversible = True` with rationale. Tested by `make migrate-down` in DoD.
- **RLS migrations** add policy + force RLS in the same transaction; covered by the standard RLS isolation test ([ADR-0025](0025-testing-strategy.md)).

### Versioning + naming
- Alembic revisions use `slug_yyyymmdd_hhmm.py`.
- Each migration's docstring documents the **shape** (Additive / Backfill / Rename phase N / Type change phase N).
- Migrations live in `apps/api/alembic/versions/`.

### Pre-launch concession
Until the first productive tenant, **migrations may take the stack down briefly** (the `make deploy` window). The Expand/Contract discipline is still required — it's a habit, not a runtime guarantee yet — but a 60-second blip is acceptable. Post-launch, zero-downtime is mandatory.

## Consequences
- (+) Every shape has a known recipe; review of a migration starts with "which shape?"
- (+) Rolling deploys ([ADR-0018](0018-rolling-deploys.md)) cannot deadlock against schema changes — code is always forward-compatible with the schema being deployed.
- (+) Backfills are independent of deploys — owner can run them off-hours, watch progress, abort without rollback.
- (+) Fiscal append-only rule is structural, not procedural.
- (−) Multi-phase migrations (rename, type change) ship in two PRs, two deploys. Friction by design.
- (−) `CREATE INDEX CONCURRENTLY` requires `transactional_ddl = False` for that revision — easy to forget; checked in code review and by a CI lint that flags non-CONCURRENT index creation.
- (−) Downgrade testing has a cost (every migration must round-trip).

## Alternatives
- **Big-bang migrations during a maintenance window** — rejected: incompatible with rolling deploys and erodes uptime as the system grows.
- **Schema-versioned APIs (e.g., separate DB per major version)** — rejected: massive complexity for an SMB ERP.
- **Tool other than Alembic (yoyo, Django migrations, raw SQL)** — rejected: Alembic is already chosen ([ADR-0010](0010-python-fastapi.md)) and integrates with SQLAlchemy autogenerate.
- **No `downgrade()` (one-way migrations)** — rejected: makes local-dev cycle painful and removes the only test of migration symmetry.

## Revisit triggers
- First productive tenant — pre-launch concession ends; zero-downtime becomes mandatory and the CI lint adds an "is this shape safe?" gate.
- Backfill exceeds 30 minutes on production data — invest in chunked / resumable backfill harness.
- A migration causes a rollback in production — incident review feeds into a sharper checklist in [`../13-operations.md`](../13-operations.md).
- Schema reaches > 100 tables — re-evaluate whether per-context migration trees are warranted.
