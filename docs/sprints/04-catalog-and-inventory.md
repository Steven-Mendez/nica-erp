# Sprint 04 — `catalog` + `inventory` with kardex + deploy

**Goal.** Create products, manage stock, view kardex valued at weighted average locally and on AWS. No new swap (everything is pure Postgres); the deploy exercises the migrations against real RDS.

Valuation method fixed by [ADR-0019](../adr/0019-kardex-inventory.md). No FIFO/LIFO or lot tracking.

---

## Dependencies

- [00](00-walking-skeleton.md) (`OutboxWriter`); [03](03-tenants-and-rls.md) (RLS).
- **Produced here, consumed later**: `inventory_writer` (outbound port from `sales` to `inventory`) is first invoked in [05](05-parties-and-sales.md) `IssueInvoice`. `StockAdjusted`/`LowStockAlerted` events are published via in-process dispatcher; real publisher arrives in [07](07-outbox-eventbridge-audit.md).
- **Does not depend** on the `taxes` context (in this sprint `Product.tax_class` is just metadata; `taxes` arrives in [06](06-taxes-payments-reports.md)).

---

## `catalog/` context

- Aggregates: `Product`, `Category`.
- VOs: `Sku`, `Barcode` (optional EAN-13 validation), `Price` (composite with `Money` + tax_class).
- `UnitOfMeasure` as a global non-tenant entity (catalog: unit, dozen, pound, kg, liter, ml, ...).
- Events: `ProductCreated`, `PriceChanged`, `ProductDeactivated`.

## `inventory/` context

- Aggregate root: `Warehouse` (warehouse identity and configuration).
- Entities under the aggregate: `StockLevel` (current balance `(product_id, warehouse_id)` with `quantity` + `avg_cost`) and `StockMovement` (append-only ledger per movement). Each use case operates on the root and maintains consistency between the inserted movement and the recomputed balance in the same transaction.
- `StockMovement` is the immutable ledger. Types: `purchase_receipt`, `sale`, `adjustment_in`, `adjustment_out`, `transfer_out`, `transfer_in`, `return_in`, `return_out`.
- `StockLevel` aggregates the ledger into a current-state view by `(product_id, warehouse_id)`:

  ```sql
  CREATE TABLE stock_levels (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL,
    product_id          UUID NOT NULL,
    warehouse_id        UUID NOT NULL,
    quantity            NUMERIC(14,4) NOT NULL DEFAULT 0,
    avg_cost            NUMERIC(14,4) NOT NULL DEFAULT 0,
    min_stock_level     NUMERIC(14,4) NOT NULL DEFAULT 0,  -- 0 = no alert
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, warehouse_id)
  );
  ```

### Valuation — weighted average

`new_average = (current_stock × current_cost + incoming_quantity × incoming_cost) / (current_stock + incoming_quantity)`

Policy by movement type:
- `purchase_receipt`, `adjustment_in` with declared `unit_cost` → recompute `avg_cost`.
- `adjustment_in` **without** `unit_cost` → rejected in the use case (the operator must declare the cost; the current average is not assumed).
- `return_in` (customer return) → quantity returns at the **cost of the original `StockMovement`** (`reverses_movement_id`). Fallback to current `avg_cost` with `cost_basis_source = 'fallback_current_avg'` if it cannot be mapped. **Does not recompute** `avg_cost`. Detail in [ADR-0019](../adr/0019-kardex-inventory.md).
- `sale`, `adjustment_out`, `transfer_out`, `return_out` → consume at the current `avg_cost` without modifying it.
- `transfer_in` → enters destination with the origin's `avg_cost`.

Events: `StockAdjusted`, `StockMoved`, `LowStockAlerted` (when the movement leaves `quantity < min_stock_level` and `min_stock_level > 0`).

---

## Cross-context communication

`catalog` writes `ProductCreated` to the outbox (same transaction that persists the product). `inventory` consumes post-commit and creates default `StockLevel`:

```python
# bootstrap (in-process in sprint 04; SQS from sprint 07 without touching the use case)
integration_event_dispatcher.subscribe(ProductCreated, create_default_stock_level)
```

`create_default_stock_level` creates `StockLevel(product_id, warehouse=default, quantity=0, avg_cost=0, min_stock_level=0)`. Idempotent via `INSERT ... ON CONFLICT (product_id, warehouse_id) DO NOTHING`. From [sprint 07](07-outbox-eventbridge-audit.md) the dispatcher is transparently replaced by `outbox publisher → EventBridge → SQS → handler`.

`catalog` does not know `inventory`. The in-process `EventBus` of `shared_kernel/` is still for intra-context domain events; between contexts: always outbox.

---

## Use cases

- `catalog`: `CreateProduct`, `UpdateProduct`, `DeleteProduct` (soft, `is_active=false`), `ListProducts`, `GetProduct`, `GetProductByBarcode`, `CreateCategory`, `ListCategories`, `ListUnitsOfMeasure`.
- `inventory`: `CreateWarehouse`, `ListWarehouses`, `AdjustStock`, `TransferStock`, `GetStockLevels`, `GetStockByProduct`, `GetKardex`.

Endpoints: [`../08-api-conventions.md` #catalog](../08-api-conventions.md#catalog) and [#inventory](../08-api-conventions.md#inventory).

## Migration 0004

Tables `products`, `categories`, `units_of_measure` (global, no tenant), `warehouses`, `stock_levels`, `stock_movements`. All tenant-scoped with RLS (see canonical pattern in [sprint 03](03-tenants-and-rls.md)). Additional seed in `permissions` + `role_permissions` (see §Permissions below).

---

## Permissions ([ADR-0022](../adr/0022-rbac-model.md))

Added to the catalog:

| Permission | Resources | Default roles |
|---|---|---|
| `product:read`, `category:read`, `inventory:read` | `Product`, `Category`, `Warehouse`, `StockLevel`, `StockMovement` | all |
| `product:write`, `category:write` | catalog | admin, owner |
| `product:delete` | soft delete | admin, owner |
| `inventory:adjust` | `AdjustStock` | admin, owner |
| `inventory:transfer` | `TransferStock` | admin, owner |
| `inventory:set-threshold` | `min_stock_level`, `Warehouse` write | admin, owner |

No hybrid ownership in this context (`scope='na'`). `salesperson` sees the catalog and stock but does not modify them — only `admin` adjusts inventory, transfers and configures thresholds. Rationale: inventory operations are an administrative responsibility, not a sales one.

---

## Frontend

Routes `/catalog/products[/new|/$id]`, `/catalog/categories`, `/inventory/warehouses[/new]`, `/inventory/stock`, `/inventory/adjustments/new`, `/inventory/kardex/$productId`. Zod validation: `adjustStockSchema` rejects empty `unit_cost` on `adjustment_in`. Rest follows README §Shared patterns.

---

## Sprint tests

- Unit: weighted average (first entry, multiple entries, mix with outflows); invariant "do not consume more stock than available" when `allow_negative=false`.
- Integration: `ProductCreated` → `StockLevel` 0/0 (in-process handler); sequence of entries with different costs updates the average.
- E2E: product + `+100 @ C$10` + `+50 @ C$12` → `avg_cost ≈ 10.67` (= `(100×10 + 50×12)/150`).

---

## Verifiable outcome (local)

```bash
curl -X POST localhost:8000/v1/warehouses ... -d '{"name":"Bodega Principal"}'
curl -X POST localhost:8000/v1/products ... -d '{"sku":"P001","name":"Coca Cola 600ml","unit":"unidad","price":25.00}'
curl -X POST localhost:8000/v1/inventory/adjustments ... -d '{"product_id":"...","warehouse_id":"...","quantity":100,"unit_cost":10.00}'
curl -X POST localhost:8000/v1/inventory/adjustments ... -d '{"...","quantity":50,"unit_cost":12.00}'
curl localhost:8000/v1/reports/kardex/<product_id> ...
# → 2 movements, balance 150u, avg_cost ≈ 10.67
```

---

## Deploy

No new swap (the in-process dispatcher is pure Python, identical on ECS).

### Terraform additions

- **Migration 0004** with RLS (pattern [sprint 03](03-tenants-and-rls.md)).
- No new modules: redeploy of the binary.

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus: at `URL/` create category "Bebidas", product SKU P001, adjustments that exercise weighted average; kardex view with 3 ledger rows. Verify `avg_cost` consistent in RDS.
