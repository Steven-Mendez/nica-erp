# ADR-0011 — UUIDv7 as aggregate primary key

**Status**: Accepted
**Date**: 2026-05-23

## Context
DDD aggregates ([ADR-0001](0001-hexagonal-architecture.md)) require identity generated in the application before `INSERT`, globally unique across tenants, opaque in URLs, and compatible with efficient B-tree indexes for tables like `outbox` ([ADR-0006](0006-transactional-outbox.md)) and `audit_log_entries`.

## Decision
**UUIDv7 as primary key for every aggregate and every outbox event.**

- Application-side generation with `uuid_utils.uuid7()`; returns a standard `uuid.UUID`.
- `IdGenerator` port in the shared kernel exposes `new_id() -> UUID`; tests inject a deterministic generator.
- Postgres: `uuid NOT NULL` columns with standard B-tree, no extensions.
- **Server-side fallback documented, not used by default**: `pg_uuidv7` extension or in-house `plpgsql` function when available in RDS. Rejected as the primary path: it would break dev/prod symmetry if extension versions differ between LocalStack/Postgres container and RDS.

## Consequences
- (+) Identity constructible in memory before persistence — compatible with DDD aggregates ([ADR-0001](0001-hexagonal-architecture.md)).
- (+) Efficient B-tree index: inserts trend toward the end. Critical for `outbox`, `audit_log_entries`, `processed_events` ([ADR-0006](0006-transactional-outbox.md)).
- (+) No overhead vs UUIDv4; same `uuid` column.
- (+) Opacity: does not reveal tenant volume in URLs.
- (+) Within a single transaction, `event_id` is generated once before INSERT; on automatic SQLA retry of the same transaction the PK violation dedupes. Cross-request idempotency (same command sent twice over HTTP) is **not** guaranteed by UUIDv7 — it requires `idempotency_keys` (see [ADR-0006](0006-transactional-outbox.md) §INSERT idempotency).
- (−) Leaks creation timestamp (48 bits). Not sensitive in this domain.
- (−) Dependency on `uuid_utils`. Mitigated: the `IdGenerator` port isolates it.
- (−) Recent standard (RFC 9562, May 2024); some DB tools display it as "unknown UUID". Cosmetic.

## Alternatives
- **UUIDv4** — rejected: random values degrade B-tree (page splits, bloat).
- **`bigserial`** — rejected: couples to the engine, exposes volume/order.
- **ULID** — rejected: not native in Postgres.
- **Snowflake IDs** — rejected: requires coordinating `machine_id`.
- **UUIDv7** (RFC 9562) — chosen: native `uuid`, time-ordered, opaque.

## Revisit triggers
- RDS ships `pg_uuidv7` or native UUIDv7 generation in the same version as LocalStack/Postgres container — server-side generation becomes viable without breaking dev/prod symmetry.
- The 48-bit timestamp leak becomes a real concern (regulatory or competitive).
