# ADR-0013 — UTC in DB and events; tenant timezone only for presentation

**Status**: Accepted
**Date**: 2026-05-23

## Context
Nicaragua runs on `America/Managua` (UTC-6, no DST), but the multi-tenant model ([ADR-0002](0002-postgres-rls.md)) does not rule out tenants in other zones. Mixing timezones breaks daily/monthly cutoffs — an invoice at 23:55 local can fall on the next UTC day and break the IVA ledger ([17 — Compliance](../17-compliance-nicaragua.md)).

## Decision
**Every temporal column is `timestamptz`; the application persists and publishes UTC; tenants have a `timezone` for presentation; fiscal cutoffs apply the tenant's zone.**

### Schema
- Every temporal column `timestamptz NOT NULL DEFAULT now()`. `timestamp` without timezone is forbidden.

### Application (Python)
- `Clock` port ([`../02-architecture.md`](../02-architecture.md)) always returns `datetime.now(UTC)`.
- Naive `datetime.now()` and `datetime.utcnow()` are forbidden; enforced by linter (`ruff DTZ`).
- Pydantic DTOs serialize with a `Z` suffix.

### Events
- `occurred_at` UTC ISO 8601 with `Z` ([ADR-0006](0006-transactional-outbox.md)); consumers apply the tenant zone when presenting.

### Tenants
- Field `timezone TEXT NOT NULL DEFAULT 'America/Managua'` (IANA); validated against `pg_timezone_names`.

### Fiscal cutoffs
- Monthly IVA ledger, daily sales, IMI ([17 — Compliance](../17-compliance-nicaragua.md)) cut **in the tenant's zone** via `(issued_at AT TIME ZONE :tenant_tz)::date`. Example: invoice `2026-06-01T03:00:00Z` (= `2026-05-31T21:00 America/Managua`) belongs to the **May** ledger.

### Frontend
- `Intl.DateTimeFormat(undefined, { timeZone: tenant.timezone })` ([ADR-0009](0009-frontend-stack.md)); centralized in `useTenantDateFormat()` ([09 — Frontend](../09-frontend.md)). The browser zone is **not** inferred.

## Consequences
- (+) No ambiguity: everything UTC in persistence, app, and events.
- (+) Tenants in other zones work immediately via the `timezone` field.
- (+) Fiscal reports correct near midnight.
- (+) Trivial cross-tenant comparisons.
- (−) Discipline: naive `datetime.now()` is a bug. Mitigated with the linter and the `Clock` port.
- (−) `AT TIME ZONE` slightly slower than fixed UTC ranges. Negligible at SME volume; materializable if it grows ([`../10-infrastructure.md`](../10-infrastructure.md)).
- (−) `tenant.timezone` assumed stable; a future change requires migration. Not an MVP scenario.
- (−) The frontend must pass the zone in every format call; oversight falls back to the browser timezone.

## Alternatives
- **Local time in the DB** — rejected: chaos when changing zones or comparing across tenants.
- **`timestamp` without timezone** — rejected: Postgres does not normalize; meaning depends on the writer.
- **`timestamptz` with per-session tz** — rejected: Postgres still stores UTC.
- **UTC in DB + frontend conversion** — chosen.

## Revisit triggers
- A tenant onboards in a timezone with DST — verify cutoff edge cases.
- Per-tenant timezone change becomes a real requirement (e.g., business moved) — needs a migration plan.
