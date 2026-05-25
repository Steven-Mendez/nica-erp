# ADR-0014 — Append-only fiscal documents; reversible soft delete for catalogs

**Status**: Accepted
**Date**: 2026-05-23

## Context
Two classes of entities with opposing requirements: **fiscal documents** (invoices, CN/DN, receipts, withholdings — see [17 — Compliance](../17-compliance-nicaragua.md)) that DGI requires to be preserved immutable, and **catalogs** (products, customers, suppliers) that change frequently and cannot be physically deleted without breaking FKs.

## Decision
**Dual policy: fiscal documents append-only; catalogs with reversible soft delete.**

### Fiscal documents — append-only

Tables: `invoices`, `invoice_items`, `credit_notes`, `debit_notes`, `customer_payments`, `withholding_certificates`, `audit_log_entries`.

- **No `DELETE`** from the application; DB role without `DELETE` grant. Housekeeping ([ADR-0006](0006-transactional-outbox.md)) touches only `outbox`, `processed_events`, `idempotency_keys`.
- **No destructive `UPDATE`**: states modeled as transitions (`draft` → `issued` → `cancelled`). Items, totals, and sequence number immutable after `issued`. Cancellation records `cancelled_at` + `cancellation_reason`; corrections via notes.
- **Cancellation with constraints**: an `Invoice` moves to `cancelled` only if no payments or notes reference it. Aggregate invariant, not UI.

### Catalogs — reversible soft delete

Tables: `products`, `customers`, `suppliers`, `units_of_measure`, `users`, `number_sequences` (via `is_active`).

- **Fields**: `active BOOLEAN NOT NULL DEFAULT true` + `deactivated_at TIMESTAMPTZ NULL` + `deactivated_by UUID NULL`.
- **`DELETE /v1/products/{id}`**: `UPDATE ... SET active=false, deactivated_at=now(), deactivated_by=:user`. `POST /v1/products/{id}/restore` reverts.
- **Listing** filters `WHERE active=true` by default; opt-in `?include_inactive=true`. Detail-by-id does **not** filter (historical invoices resolve the name).
- **Rule**: an inactive product/customer cannot be used in a new invoice — validated in the `CreateDraftInvoice` use case. Historical records untouched. Restoring does not recover implicit relationships (e.g., price lists).

### `audit_log_entries`
Append-only without soft delete. Long retention via partitioning and archival to S3 + Glacier ([`../10-infrastructure.md`](../10-infrastructure.md)).

## Consequences
- (+) Meets DGI obligation: fiscal records preserved with no risk of accidental deletion.
- (+) Referential integrity: FKs to `customers`/`products` never break.
- (+) UX: deactivate a customer without fear, reversible.
- (+) Auditing: `deactivated_at`/`deactivated_by` answer who and when.
- (+) DB defense: no `DELETE` grant prevents catastrophic bugs.
- (−) `WHERE active=true` in every listing. Mitigated with a `SoftDeletableMixin`.
- (−) Catalogs grow monotonically. Acceptable at SME volume.
- (−) Restoring a reused SKU generates a uniqueness conflict; validated on the restore endpoint.
- (−) Assumes 5-year DGI retention; verify against the current Ley de Concertación Tributaria ([17 — Compliance](../17-compliance-nicaragua.md)).
- (−) `audit_log_entries` requires partitioning to avoid degradation; planned, not implemented in MVP.

## Alternatives
- **Universal hard delete** — rejected: illegal for fiscal records; breaks FKs.
- **Separate archive table** — rejected: double schema, over-engineering.
- **Pure event sourcing** — rejected: complexity and storage.
- **Cascade delete with triggers** — rejected: loses auditing.
- **Universal soft delete with variants** — chosen.

## Revisit triggers
- `audit_log_entries` size requires partitioning sooner than planned (write latency or vacuum cost noticeable).
- DGI retention rules change — re-evaluate archive strategy.
