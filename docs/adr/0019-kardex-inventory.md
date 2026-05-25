# ADR-0019 — Inventory valuation by weighted moving average

**Status**: Accepted
**Date**: 2026-05-23

## Context
The `inventory` context ([04 — Domain model](../04-domain-model.md)) needs a valuation method. It impacts COGS, the inventory balance on the books, operational load when recording movements, and schema complexity. Nicaragua does not mandate a single method but requires consistency: changing methods later requires fiscal authorization. Decision must be fixed before [sprint 04](../sprints/04-catalog-and-inventory.md).

## Decision
**Kardex valued by weighted moving average. Balance `(quantity, unit_cost)` per `(tenant_id, product_id, warehouse_id)`.**

- Inflows with cost (`purchase_receipt`, `adjustment_in` with cost) recompute:
  ```
  new_qty       = old_qty + in_qty
  new_unit_cost = (old_qty * old_unit_cost + in_qty * in_unit_cost) / new_qty
  ```
- Outflows (`sale`, `adjustment_out`, `transfer_out`) discount at the current `unit_cost`; the movement captures the applied cost.
- `return_in`: reintegrates at the cost of the original outflow movement; if it cannot be mapped, it uses the current average and is tagged `cost_basis_source='fallback_current_avg'`.
- Movements without a reported cost are rejected at the domain layer.
- `quantity` and `avg_cost` stored as `NUMERIC(14, 4)` (canonical schema in [sprint 04](../sprints/04-catalog-and-inventory.md)); reports round to 2 decimals.

## Consequences
- (+) Operationally simple: the user records quantity and cost; no lots to pick on outflow.
- (+) Cheap computation: one row per SKU, no walking a lot stack.
- (+) Aligned with general commerce (stationery, hardware, non-perishable food).
- (+) Acceptable fiscally and accounting-wise under IFRS for SMEs.
- (−) No historical precision to "rewind" the exact cost of a sold unit (mitigated: the kardex stores the `unit_cost` applied on each outflow).
- (−) Not suitable for perishables where physical FIFO is regulatory (pharma, dated food). Evaluate a per-product configurable method if it comes up.
- (−) `return_in` with fallback introduces small distortion when it cannot be linked to its origin; this is tagged.
- (−) Switching method later requires migration + notice to DGI + recomputed balances. Hence the ADR.

Detailed kardex operation in [sprint 04](../sprints/04-catalog-and-inventory.md).

## Alternatives
- **FIFO** — rejected for MVP: requires lot tracking; useful for perishables, not essential for general commerce.
- **LIFO** — rejected: forbidden under IFRS for financial reporting.
- **Specific identification per lot** — rejected: over-engineering for light SKUs.
- **Weighted moving average** — chosen: one `(quantity, unit_cost)` balance per SKU.

## Revisit triggers
- A tenant onboards inventory of dated/perishable goods where FIFO is regulatory.
- DGI changes the rules on valuation method changes (e.g., simpler reclassification).
- Cost distortion from `fallback_current_avg` becomes material in audit reviews.
