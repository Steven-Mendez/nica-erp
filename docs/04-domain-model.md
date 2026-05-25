# 04 — Domain Model

High-level view of the data shape the system stores. For the architectural rules that govern how this is laid out in code see [02 — Architecture](02-architecture.md); for the per-context responsibilities see [03 — Bounded Contexts](03-bounded-contexts.md); for the ADRs that constrain identifiers, soft delete, and time, see the cross-references below.

This document is not the schema. The schema lives in `apps/api/alembic/versions/`. This document is what you'd want to know **before** opening a migration.

---

## Identifiers

- **Every aggregate root has a UUIDv7 primary key.** Temporally ordered, B-tree friendly. [ADR-0011](adr/0011-uuidv7-identifiers.md).
- **Tenant scoping**: every domain table that holds tenant data has a `tenant_id UUID NOT NULL` and an RLS policy. The set of non-tenant-scoped tables is small and listed in [05 — Multi-tenancy](05-multi-tenancy.md).
- **External references** (Cognito `sub`, RUC, third-party invoice IDs) live in dedicated columns, never as primary keys.

---

## Time

- **All timestamps are `TIMESTAMPTZ` storing UTC.** [ADR-0013](adr/0013-utc-everywhere.md).
- **Tenant timezone** is stored on `tenants.timezone` (default `America/Managua`) and applied only at presentation/reporting time.
- **Fiscal cutoffs** (monthly VAT, IR accumulation) use `AT TIME ZONE tenants.timezone` in the query, never in the model.

---

## Deletion

[ADR-0014](adr/0014-soft-delete.md) draws a hard line:

| Class | Policy |
|---|---|
| **Fiscal documents** (`Invoice`, `CreditNote`, `DebitNote`, `CustomerPayment`, `Withholding`, `audit_log_entries`) | Append-only. No `DELETE` ever. Cancellations are a state transition (`cancelled_at`, `cancellation_reason`); credit notes reverse, they don't erase. |
| **Catalog & infrastructure** (`Product`, `Category`, `Warehouse`, `Customer`, `Supplier`, `TaxConfig`) | Soft delete via `active BOOLEAN` + `deactivated_at TIMESTAMPTZ`. Restorable by toggling. |
| **Operational** (`Session`, `Notification`, queue rows) | Hard delete by retention policy. |

The application layer never issues `DELETE` against fiscal tables. Backed by both code review and DB grants (deferred until first productive tenant per [ADR-0029](adr/0029-disaster-recovery-posture.md)).

---

## Aggregates by context

This mirrors [03 — Bounded Contexts](03-bounded-contexts.md) but focuses on the data shape rather than the responsibilities.

### `identity`
- `User` — extended profile (`display_name`, `locale`, `timezone`, `preferences`), `external_sub` (Cognito `sub` or local IdP id). Tenant-agnostic.
- `auth_local_users` — local IdP credentials, only present in dev (`APP_ENV=local`).

### `tenants`
- `Tenant` — `name`, `timezone`, `status` (`provisioning`/`active`/`suspended`/`purged`, per [ADR-0026](adr/0026-tenant-lifecycle.md)), `created_at`, `suspended_at`, `purged_at`.
- `TenantMember` — `(tenant_id, user_id, role)`; role is one of the five fixed roles in [06 — Security Model](06-security-model.md).
- `Invitation` — `email`, `role`, `token_hash`, `expires_at`.

### `catalog`
- `Product` — `sku` (unique per tenant), `name`, `description`, `unit_of_measure`, `active`.
- `Category` — hierarchical via `parent_id`; deactivation cascades by policy in code, not by FK.

### `inventory`
- `Warehouse` (aggregate root) — physical location; `active`. `StockLevel` and `StockMovement` are entities under this root.
- `StockLevel` — `(tenant_id, product_id, warehouse_id)` unique. Holds `quantity` and `unit_cost` (the running weighted-average per [ADR-0019](adr/0019-kardex-inventory.md)).
- `StockMovement` — append-only ledger. `kind` (`receipt`, `issue`, `adjustment`, `transfer`), `quantity`, `unit_cost_at_move`, `reverses_movement_id` (for adjustments).

### `parties`
- `Customer` — `legal_name`, `trade_name`, `ruc`, `is_retainer` (IR withholding agent), `fiscal_address`, contact channels.
- `Supplier` — same shape; separate aggregate to keep their lifecycles independent.

### `sales`
- `Invoice` — multi-aggregate group:
  - `Invoice` — `customer_id`, `lines[]` (with snapshotted product info), `subtotal`, `vat_total`, `total`, `status` (`draft`, `issued`, `cancelled`), `issued_at`, `created_by_user_id`.
  - `NumberSequence` — `(tenant_id, doc_type, series)` with `next_number` allocated via `SELECT FOR UPDATE` ([ADR-0008](adr/0008-for-update-sequence-allocation.md)).
  - `DgiAuthorization` — independent lifecycle, tracks fiscal authorization metadata.
- `Quotation` — pre-invoice; converts to `Invoice` on accept; ownership-scoped.
- `CreditNote`, `DebitNote` — reverse/adjust prior invoices, append-only.

### `taxes`
- `TaxConfig` (aggregate) — per tenant: IVA rate, IR thresholds, IMI rate, effective dates. Tenant-scoped (RLS).
- `tax_withholdings` (ledger, not an aggregate) — append-only row written by `sales` at invoice issuance per withheld line. Owned by `taxes` for read/report purposes.

### `payments`
- `CustomerPayment` — applied to one or more invoices; ownership-scoped via `recorded_by_user_id`.
- `AccountsReceivable` — derived view; not an aggregate.

### `reports`
- No aggregates. Read-only projections (`vat_book`, `withholding_summary`, `imi_summary`, `sales_by_period`).

### `audit`
- `AuditLogEntry` — append-only. `(tenant_id, actor_id, action, resource_type, resource_id, payload jsonb, occurred_at)`. Retained 5 years per [ADR-0017](adr/0017-backups-pitr.md).

### `notifications`
- `Notification` — per-user inbox row; owner is the recipient.
- `NotificationPreference` — per-user opt-in/out matrix.

### Cross-context: outbox
- `outbox_events` — see [07 — Events and outbox](07-events-and-outbox.md). Lives in `shared_kernel`, written atomically with the originating aggregate.

---

## Invariants (cross-cutting)

These are the rules a reader of any single table can't infer from the schema alone:

1. **Tenant integrity** — every domain row's `tenant_id` matches the `tenants.id` of an active or provisioning tenant. RLS enforces at read; application layer asserts at write.
2. **Number sequence atomicity** — `Invoice.number` is allocated inside the same transaction as `Invoice` persistence, via `SELECT FOR UPDATE` on `number_sequences`. No gaps, no duplicates.
3. **Fiscal append-only** — once `Invoice.status = 'issued'`, only `cancelled_at` may be set. No other column changes. Same for `CreditNote`, `DebitNote`, `CustomerPayment`, `Withholding`.
4. **Kardex consistency** — `StockLevel.quantity` equals `SUM(StockMovement.quantity)` for the matching `(tenant_id, product_id, warehouse_id)`. A periodic reconciliation job (sprint 09) verifies.
5. **Number sequence monotonicity** — `number_sequences.next_number` only increases. There is no rollback path.
6. **Ownership consistency** — `created_by_user_id` (and equivalents) must be a `TenantMember` of the same tenant. Enforced by FK + application check.
7. **Soft-delete cascade** — deactivating a `Product` does not delete `StockLevel` rows; they remain queryable; new `StockMovement`s are rejected.
8. **Audit completeness** — every state-changing use case writes one `AuditLogEntry` in the same transaction.

---

## What this document is not

- Not the ER diagram. (Generated from migrations; lives under `docs/assets/erd.png` once sprints fill it in.)
- Not the OpenAPI schema. ([08 — API Conventions](08-api-conventions.md) points at the generated `openapi.json`.)
- Not exhaustive — sprints add columns; the per-sprint doc owns its detail. This file owns the **shape** and the **invariants**.

## References
- [ADR-0011](adr/0011-uuidv7-identifiers.md) — UUIDv7 PKs
- [ADR-0013](adr/0013-utc-everywhere.md) — UTC everywhere
- [ADR-0014](adr/0014-soft-delete.md) — Soft delete vs append-only
- [ADR-0008](adr/0008-for-update-sequence-allocation.md) — Number sequence allocation
- [ADR-0019](adr/0019-kardex-inventory.md) — Weighted-average kardex
- [ADR-0026](adr/0026-tenant-lifecycle.md) — Tenant lifecycle states
- [ADR-0028](adr/0028-data-migration-strategy.md) — How schema changes ship
