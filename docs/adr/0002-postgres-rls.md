# ADR-0002 — Multi-tenancy pool with Postgres RLS

**Status**: Accepted
**Date**: 2026-05-23

## Context
A single instance serves multiple SMBs; an application bug must not expose cross-tenant fiscal data.

## Decision
Pool + RLS as defense in depth. Every per-tenant table carries `tenant_id UUID NOT NULL` with `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` and a policy `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`. FastAPI middleware emits `SET LOCAL app.tenant_id = '<uuid>'` at the start of every transaction, reading `custom:active_tenant` from the JWT. Global tables without RLS: `users`, `tenants`, `tenant_members`, `units_of_measure`. Outbox has no RLS but carries `tenant_id` — the publisher is a system process (see [ADR-0006](0006-transactional-outbox.md)).

## Consequences
- (+) One DB, one migration; cheapest option.
- (+) If the app omits `WHERE tenant_id`, RLS filters before any row is returned.
- (+) Compatible with PgBouncer in `transaction` mode (`SET LOCAL` releases on COMMIT). `SET` (session) is forbidden for tenant-scoped variables.
- (−) Every request requires an explicit transaction.
- (−) System cross-tenant reports require a role with `BYPASSRLS` (out of MVP scope).

## Alternatives
- **Silo (DB per tenant)** — rejected: unsustainable operational cost (N backups, N upgrades).
- **Bridge (schema per tenant)** — rejected: N migrations, per-session `search_path`.
- **Pool (one DB, `tenant_id` + RLS)** — chosen.

## Revisit triggers
- A tenant requires data residency or a dedicated DB for regulatory reasons.
- Tenant count or per-tenant data volume makes a single Postgres instance the bottleneck.
- A consistent need for `BYPASSRLS` cross-tenant analytics emerges — signal to introduce a read-only warehouse rather than weaken policies.

Detail in [`../05-multi-tenancy.md`](../05-multi-tenancy.md).
