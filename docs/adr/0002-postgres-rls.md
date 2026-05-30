# ADR-0002 — Multi-tenancy pool with Postgres RLS

**Status**: Accepted
**Date**: 2026-05-23

## Context
A single instance serves multiple SMBs; an application bug must not expose cross-tenant fiscal data.

## Decision
Pool + RLS as defense in depth. Every per-tenant table carries `tenant_id UUID NOT NULL` with `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` and a policy whose **`USING` and `WITH CHECK` clauses share the same expression** `tenant_id = current_setting('app.tenant_id', true)::uuid` (the `true` flag makes the GUC return `NULL` when unset, so bootstrap/migrations don't break). FastAPI middleware emits `SET LOCAL app.tenant_id = '<uuid>'` and `SET LOCAL app.current_user_id = '<uuid>'` at the start of every transaction, reading `custom:active_tenant` and the resolved `sub` from the JWT.

**Global tables without RLS** (system catalogs cross tenants by design): `users`, `tenants`, `units_of_measure`, `permissions`, `role_permissions`, `outbox`, `processed_events`, `idempotency_keys`. The outbox/processed-events/idempotency-keys triplet is read by system processes (publisher, dispatcher) that operate across tenants ([ADR-0006](0006-transactional-outbox.md)); their `tenant_id` column is a filter, not an isolation boundary, and access is restricted by **DB role**, not policy.

**Tenant-scoped tables with a special policy**: `tenant_members` carries RLS with `USING (user_id = current_setting('app.current_user_id', true)::uuid OR tenant_id = current_setting('app.tenant_id', true)::uuid)` so a user can read their own memberships before any tenant is active (needed for the post-login tenant picker). `WITH CHECK` keeps the canonical `tenant_id = current_tenant` expression — a user cannot insert/update a membership row for a tenant other than the active one.

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
