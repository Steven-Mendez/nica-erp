# ADR-0008 — Correlative numbering with `FOR UPDATE` lock

**Status**: Accepted
**Date**: 2026-05-23

## Context
DGI Nicaragua requires strict correlative numbering with no gaps and no duplicates, per authorized range, per tenant, per document type. If the commit aborts after assigning a correlative, the number must be reused.

## Decision
Inside the command's transaction: `SELECT ... FOR UPDATE` on the `(tenant_id, document_type, is_active=true)` row of `number_sequences`, validate against `range_to`, assign `next_number`, `UPDATE next_number = next_number + 1`, continue with the rest (insert invoice, stock, outbox), COMMIT. The lock is released on commit/rollback; `statement_timeout` (~10 s) protects against hangs.

## Consequences
- (+) Zero gaps, zero duplicates, zero correlatives lost on rollback; DGI-compliant.
- (+) Modelable as a clean aggregate (`NumberSequence`); multiple ranges coexist (`is_active` + validity).
- (−) Requests for the same `(tenant, document_type)` are serialized; throughput is comfortable for the expected pace (~ 1 invoice/min per cashier).
- (−) Slow queries inside the workflow extend the lock — mitigated by computing before the `FOR UPDATE` when possible.

## Alternatives
- **Postgres `SEQUENCE`** — rejected: global, increments outside the transaction (rollback creates gaps), does not handle dated ranges.
- **Redis `INCR`** — rejected: distributed state that can be lost, extra dependency.
- **Optimistic locking with retry** — rejected: complicates logic for marginal gain at the expected volume.
- **`number_sequences` table with `SELECT ... FOR UPDATE` on the active row** — chosen.

## Revisit triggers
- Concurrent issuance rate per `(tenant, document_type)` rises to the point where serialization becomes the bottleneck (e.g., multiple cashiers per second).
- DGI regulation changes the correlative model (e.g., centralized allocation, electronic invoicing with server-assigned numbers).
- A second domain needs gap-free numbering and the per-row lock pattern starts costing more than a dedicated allocator service.

Detail in [`../17-compliance-nicaragua.md §NumberSequence`](../17-compliance-nicaragua.md#numbersequence).
