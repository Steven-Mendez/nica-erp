# 03 — Bounded Contexts

Autonomous contexts under `contexts/`. Two communication paths: **read-only outbound port** (synchronous) and **integration event** (asynchronous). Pattern in [02 § Operating rules](02-architecture.md#operating-rules).

---

## Map

| Context | Responsibility | Aggregates | Events |
|---|---|---|---|
| **identity** | Auth, profile, password reset. `IdentityProvider` adapter. | `User` | `UserRegistered`, `PasswordReset` |
| **tenants** | Small-business companies + fiscal (RUC, DGI authorization), memberships, invitations. | `Tenant`, `Membership`, `Invitation` | `TenantCreated`, `MemberInvited`, `MemberJoined` |
| **catalog** | Products, categories, units, prices. | `Product`, `Category` | `ProductCreated`, `PriceChanged`, `ProductDeactivated` |
| **inventory** | Stock per warehouse, kardex, weighted average valuation. | `Warehouse` (root; entities: `StockLevel`, `StockMovement`) | `StockAdjusted`, `StockMoved`, `LowStockAlerted` |
| **parties** | Customers and suppliers with NI fiscal data. | `Customer`, `Supplier` | `CustomerCreated`, `SupplierCreated` |
| **sales** | Quotations, **invoices**, CN/DN, DGI sequential numbering. | `Invoice`, `CreditNote`, `DebitNote`, `Quotation`, `NumberSequence` | `InvoiceIssued`, `InvoiceCancelled`, `CreditNoteIssued`, `DebitNoteIssued`, `NumberSequenceLowAlerted` |
| **taxes** | VAT/IR/IMI/non-resident withholding calculation. Owns tax rates per tenant + append-only withholding ledger. | `TaxConfig` | — |
| **payments** | AR, application to invoices, advances, reversals. | `CustomerPayment` | `PaymentReceived`, `PaymentApplied`, `PaymentReversed`, `InvoicePaid` |
| **reports** | VAT book, kardex, sales, withholdings, AR. Pure queries. | — | — |
| **notifications** | Transactional + in-app email, per-user preferences. | `Notification`, `NotificationPreference` | `NotificationSent`, `NotificationFailed` |
| **audit** | Immutable event log. Consumes the whole bus. | `AuditLogEntry` | (consumes) |

---

## Per-context notes

**identity.** `users` table with `external_sub` (logical FK to the active IdP's `sub`: Cognito in prod, local IdP in dev) + extended profile. Use cases: `RegisterUser`, `ConfirmSignup`, `Authenticate`, `RefreshToken`, `ChangePassword`, `ForgotPassword`, `ResetPassword`, `UpdateProfile`. Detail in [06](06-security-model.md).

**tenants.** `Tenant.tax_config` (jsonb) stores regime, DGI authorization, municipality, withholder yes/no. Active tenant switch: `custom:active_tenant` claim in JWT via `POST /v1/tenants/{id}/switch` (Cognito `AdminUpdateUserAttributes` or local equivalent). `Invitation` by email is associated or kept pending until registration.

**catalog.** Unique SKU per tenant. On creating `Product`, publishes `ProductCreated` → `inventory` creates `StockLevel` at 0 in the default warehouse. `UnitOfMeasure` is a global catalog.

**inventory.** `StockMovement` forms the kardex with reason (adjustment, transfer, sale, return, receipt). Weighted average valuation ([ADR-0019](adr/0019-kardex-inventory.md)).

**parties.** `Customer` and `Supplier` separate (different rules and flows). Fiscal data: document type, RUC/cédula, address, withholder/exempt.

**sales — `Invoice`.** States `draft`, `issued`, `paid`, `partially_paid`, `cancelled`. In `draft` it is edited freely. `issue` executes **atomically** in one transaction:

1. `FOR UPDATE` lock on the active `NumberSequence` of the document type.
2. Allocation of the next sequence number (if the range is exhausted → business error).
3. Tax calculation per line via the `tax_calculator` port.
4. Stock deduction via the `inventory_writer` port.
5. Insertion of `invoice + items + tax_lines`.
6. Insertion of `InvoiceIssued` row in `outbox`.
7. Commit.

`cancel` only if `issued` and no payments applied → `InvoiceCancelled`. CN/DN reference `Invoice` and follow their own sequence (immutable; rectification = inverse CN/DN). `Quotation` has its own lifecycle and can be converted to draft `Invoice`. `NumberSequence` models DGI-authorized ranges ([17](17-compliance-nicaragua.md), [ADR-0008](adr/0008-for-update-sequence-allocation.md)).

**taxes.** `TaxConfig` aggregate per tenant holds active VAT/IR/IMI rates and thresholds. `TaxCalculator` (domain service) receives lines + customer/supplier profile + active rules, returns `TaxBreakdown` (VO). `tax_withholdings` is an append-only ledger written by `sales` at invoice issuance via the `withholding_writer` outbound port — taxes owns the table and read queries but does not produce aggregates from it.

**payments.** Receipts (cash, transfer, check, card). FIFO or manual application to invoices; reversal unapplies. AR = sum of issued, non-cancelled, not fully paid invoices (direct query).

**reports.** Queries that **compose results published by other contexts** (`sales.queries.SalesSummary`, `inventory.queries.Kardex`…). Does not read foreign tables. Wiring can route queries to an RO replica without `reports` knowing. Covers: sales summary, sales by product/customer, inventory valuation, kardex, VAT book, IR withholdings. Closed months are immutable → materialized view when justified ([10 § Reports](10-infrastructure.md#reports-and-vat-book)).

**notifications.** Lambda worker subscribed to `UserRegistered`, `MemberInvited`, `InvoiceIssued`, `LowStockAlerted`, `NumberSequenceLowAlerted`. Jinja2 templates in code. SES prod / Mailpit dev.

**audit.** Lambda consumes the **entire** bus. Per-consumer idempotency in `audit.processed_events` with UNIQUE `event_id`. `GET /v1/audit-log` for admin with filters. Partitioned by month over `occurred_at` past ~10 M rows; archived to S3 + Glacier ([10 § Audit log](10-infrastructure.md#audit-log-partitioning-and-archival)).

---

## Adding a new module

For `purchases`:

1. New folder `contexts/purchases/` with `domain/`, `application/`, `adapters/`.
2. Outbound ports: `supplier_lookup` → `parties` (read-only); `inventory_writer` (sums entries) — same port as `sales`; `tax_calculator` with `calculate_for_purchase` in addition to `calculate_for_sale`; `event_publisher` (`PurchaseOrderIssued`, `GoodsReceived`, `SupplierInvoiceRecorded`).
3. **Zero modifications** to `sales`, `parties`, `inventory`, `taxes`.
4. Alembic migration with its tables (RLS per the [sprint 03](sprints/03-tenants-and-rls.md) pattern).
5. Endpoints under `/v1/purchases/*`.
6. When `accounting` enters, it consumes events from **all** contexts (including `purchases`) to generate journal entries.

This is where hexagonal + bounded contexts pay off: third or fourth module without rewriting anything.
