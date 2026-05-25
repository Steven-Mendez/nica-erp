# Sprint 06 — `taxes` + `payments` + `reports` + BCN scraper Lambda + deploy

**Goal.** IR withholdings, IMI, monthly official VAT book, payments, accounts receivable. Cycle: invoice → partial payment → AR. `FxRateProvider` port swap: local fixture ↔ Lambda in VPC with daily scheduled rule that scrapes BCN and persists into `fx_rates`. Closes with VAT book downloaded from the CloudFront URL and the first `fx_rates` row populated.

---

## Dependencies

- [03](03-tenants-and-rls.md) (RLS); [04](04-catalog-and-inventory.md) (`Product.tax_class`); [05](05-parties-and-sales.md) (`IssueInvoice` which here delegates to the `tax_calculator` port).
- **Produced here, consumed later**: `fx_rates` populated by daily Lambda. Compliance and VAT book format: [`../17-compliance-nicaragua.md`](../17-compliance-nicaragua.md).

---

## `taxes/` context

Pure service; persists only `tax_config` per tenant.

### `TaxCalculator` — per-invoice calculations

- **15% VAT** per line. Exemptions: exempt customer, exempt product, zero rate.
- **IR withholdings** if `customer.is_retainer`:
  - 2% goods/services when monthly accumulated `(retainer=customer.id, provider=tenant.id)` exceeds C$1,000. Threshold per retainer customer (two customers do not accumulate between them).
  - **Reset**: accumulated per calendar month in tenant timezone ([ADR-0013](../adr/0013-utc-everywhere.md)). No cleanup job; query `SUM(amount) WHERE issued_at >= date_trunc('month', current_date AT TIME ZONE tenant.timezone)` recomputes on each calculation. In `taxes/adapters/queries/monthly_ir_accumulated.py`.
  - 10% professional services (no threshold); 3% technical services (no threshold).
  - 30% non-residents without treaty (MVP placeholder — not E2E tested because it requires modeling bilateral treaties, out of scope).
- **IMI 1%** (configurable per tenant). One `imi_rate` inherited from `tenant.municipality`. Multi-municipality is deferred.

Returns `TaxBreakdown` (VO) with aggregate and per-line totals. Detailed computation in [`../17-compliance-nicaragua.md`](../17-compliance-nicaragua.md).

### Config

```sql
CREATE TABLE tax_config (
  tenant_id        UUID PRIMARY KEY REFERENCES tenants(id),
  iva_rate         NUMERIC(5,4) NOT NULL DEFAULT 0.1500,
  imi_rate         NUMERIC(5,4) NOT NULL,  -- no SQL default; CreateTaxConfig populates from tenants.municipality
  ir_rates         JSONB NOT NULL,                 -- {"goods":0.02,"professional_services":0.10,...}
  ir_threshold_monthly  NUMERIC(12,2) NOT NULL DEFAULT 1000.00,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> The `imi_rate` column has no SQL default — `CreateTaxConfig` (invoked during tenant onboarding) populates it from `tenants.municipality` (1.0% Managua, 0.5–1% other municipalities per [§ IMI](../17-compliance-nicaragua.md#imi--municipal-tax-on-income)). Operators can override per tenant.

RLS applied (pattern [sprint 03](03-tenants-and-rls.md)) even though the PK is already `tenant_id` — defense in depth.

---

## `sales` refactor

`IssueInvoice` replaces the inline computation with the outbound `tax_calculator` port (in-process adapter in `taxes`):

```python
tax_breakdown = await tax_calculator.calculate_for_sale(
    tenant_id=tenant_id, lines=invoice.items_input,
    customer=customer.tax_profile, emission_date=clock.today(),
)
```

Packages: port in `sales/application/ports/outbound/tax_calculator.py`; adapter in `taxes/adapters/inbound/in_process/tax_calculator_in_process.py`; wiring in `bootstrap/container.py`. Synchronous in-process collaboration `sales → port ← taxes`.

---

## `payments/` context

- Aggregate: `CustomerPayment`. Fields: `id`, `tenant_id`, `customer_id`, `amount`, `currency`, `method` (cash/transfer/check/card/other), `reference`, `received_at`, `applied_to` (list `(invoice_id, amount)`).
- Application to invoices: FIFO automatic or manual.
- Reverse: `ReversePayment` un-applies.
- Events: `PaymentReceived`, `PaymentApplied`, `InvoicePaid` (100%), `PaymentReversed`.

## Use cases

- `taxes`: `GetTaxConfig`, `UpdateTaxConfig`, `QuoteTaxes` (preview without persisting).
- `payments`: `ReceivePayment`, `ApplyPaymentToInvoices`, `ReversePayment`, `GetAccountsReceivable`, `GetCustomerOpenInvoices`.

## `reports/` context

Queries only (pragmatic CQRS, no aggregates). `format=json|csv|xlsx`.

- `sales-summary`, `sales-by-product`, `sales-by-customer` (per range).
- `inventory-valuation` (stock at current average cost).
- `kardex/<product_id>` per range.
- **`vat-book?month=YYYY-MM`** — monthly VAT book in official DGI format; `format=json|csv|xlsx` like the rest.
- `retentions?from=&to=` — withheld IR (input for withholding certificates).
- `imi?from=&to=` — monthly IMI.

## Migration 0006

Tenant-scoped tables (with RLS): `tax_config`, `customer_payments`, `payment_applications`, **`tax_withholdings`** (one row per withheld IR line at invoice issuance — direct input of `/v1/reports/retentions` and future withholding certificate).

`customer_payments` carries `recorded_by_user_id UUID NOT NULL` for hybrid ownership.

Global table (no tenant_id): `fx_rates` populated by the daily Lambda.

Additional seed in `permissions` + `role_permissions` (see §Permissions below).

---

## Permissions ([ADR-0022](../adr/0022-rbac-model.md))

Added to the catalog:

| Permission | Resources | Default roles |
|---|---|---|
| `tax-config:read` | `TaxConfig` | salesperson+ |
| `tax-config:write` | edit rates | admin, owner |
| `tax-quote:run` | `POST /v1/taxes/quote` (preview) | salesperson+ |
| `customer-payment:read` (own), `customer-payment:read-all` | `CustomerPayment` | salesperson (own); accountant+ (all) |
| `customer-payment:write` | register payment | salesperson+ |
| `customer-payment:apply` | apply to invoices | accountant+ |
| `customer-payment:reverse` | reverse with `PaymentReversed` | accountant+ |
| `accounts-receivable:read` | aggregate AR and per customer | salesperson+ |
| `report:sales`, `report:inventory` | operational reports | all |
| `report:vat-book` | monthly VAT book | accountant+ |
| `report:retentions` | withheld IR | accountant+ |
| `report:imi` | monthly IMI | accountant+ |

`CustomerPaymentRepository` inherits from `OwnedAggregateRepository` (see [`../06-security-model.md` §Ownership filter](../06-security-model.md#ownership-filter-in-the-query-layer)). Fiscal reports (`vat-book`, `retentions`, `imi`) require role `accountant+` because they consolidate cross-tenant data.

---

## Frontend

Routes `/taxes/{config,quote,iva-book,retentions,imi-report}`, `/payments/customer-payments[/new|/$id]`, `/accounts-receivable[/$customerId]`, `/reports/{sales-summary,sales-by-product,sales-by-customer,inventory-valuation}`. "Download XLSX" invokes `GET /v1/reports/vat-book?month=YYYY-MM&format=xlsx` with `responseType` blob. Zod validation: `taxConfigSchema` (`iva_rate, imi_rate ∈ [0,1]`, `ir_threshold_monthly ≥ 0`); `receivePaymentSchema` (`amount > 0`, `method` enum, `reference` required except `cash`). Rest follows README §Shared patterns.

---

## Sprint tests

- Unit: `TaxCalculator` (general/exempt/zero-rate VAT, IR with/without threshold, IMI Managua/other); FIFO of payments; reverse un-applies.
- Integration: invoice with retainer → `total_to_charge = total_after_taxes - ir_withheld`.
- E2E: invoice → partial payment → AR = total − paid; VAT book of the month includes the invoice.

---

## Exit criteria

Every criterion must be a command that returns exit 0 or an evident value.

- `pytest -m unit` exit 0, `domain/` + `application/` coverage ≥ 70%
- `pytest -m integration -k "taxes or payments or reports"` exit 0
- `pytest -m e2e -k "issue_and_pay or vat_book"` exit 0
- `ruff check`, `mypy --strict`, `pnpm typecheck`, `pnpm lint --max-warnings=0` all exit 0
- `make migrate && make migrate-down && make migrate` exit 0
- `make deploy` exit 0, post-deploy checklist passes (see [README §Post-deploy verification](README.md#post-deploy-verification)), `make destroy` exit 0
- **N+1 gate on `compute_ir_for_invoice`** — see [`../14-testing.md` §N+1 gate](../14-testing.md#n1-gate). The monthly IR accumulation query must not scale linearly with invoice line count.

---

## Verifiable outcome (local)

```bash
curl -X POST localhost:8000/v1/customers ... -d '{"name":"Gran Contribuyente SA","ruc":"...","is_retainer":true}'
# IR base: 2% over subtotal WITHOUT VAT (standard DGI practice).
# subtotal 1000 → VAT 150 → IR 20 → total_to_charge 1130.
curl -X POST localhost:8000/v1/customer-payments ... -d '{"customer_id":"...","amount":500,"method":"transfer","reference":"..."}'
curl -X POST localhost:8000/v1/customer-payments/<id>/apply ... -d '{"applications":[{"invoice_id":"...","amount":500}]}'
curl localhost:8000/v1/accounts-receivable/<customer_id> ...                    # → balance 630
curl 'localhost:8000/v1/reports/vat-book?month=2026-05&format=xlsx' ... -o libro-iva.xlsx
```

---

## Deploy

BCN scraper as Lambda with daily scheduled rule + downloadable VAT book.

### Terraform additions

- **Lambda `fx_scraper`** (first worker Lambda): container image from the same ECR, `entrypoint = ["python","-m","bootstrap.entrypoints.fx_scraper"]`. Runs in VPC `private-app-a` with SG `lambda-sg` (egress 443 via NAT to BCN; access to RDS via private network).
- **EventBridge scheduled rule `fx_scraper_daily`**: `cron(0 12 * * ? *)` (06:00 Managua = 12:00 UTC). Exponential retry inside the run with `tenacity` (3 attempts, base 2 s, max 16 s, jitter 0–1 s) before returning an error to the Lambda. AWS does not retry the scheduled invocation (`MaximumRetryAttempts=0`); SNS alert `nica-erp-alerts` after 3 consecutive daily runs without writing a row to `fx_rates`.
- **IAM**: role `nica-erp-lambda-fx-role` with `AWSLambdaVPCAccessExecutionRole`, `ssm:GetParameter` + `kms:Decrypt` (alias `aws/ssm`) over `/nica-erp/db/master` ([ADR-0021](../adr/0021-ssm-parameter-store.md)) and `events:PutEvents` (future).

### Wiring

```python
def build_fx_rate_provider() -> FxRateProvider:
    if settings.app_env == "local":
        return FxRateProviderMock(fixed_rate=settings.fx_rate_usd_nio)
    return FxRateProviderBcn(client=httpx.AsyncClient(), session=SessionLocal)
```

In AWS the provider reads the latest `fx_rates` row populated by the Lambda; scraping happens outside the request path.

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus:
- Config `tax_config` (iva 0.15, imi 0.01), mark customer `is_retainer=true`, accumulate sales > C$1,000, issue invoice with 2% IR, partial payment → `partially_paid`, download VAT book XLSX.
- `aws logs filter-log-events --log-group-name /aws/lambda/nica-erp-fx ...` shows at least one `fx_rate_updated: 36.X`.
- `aws lambda invoke --function-name nica-erp-fx ... /tmp/out.json` → `{"statusCode":200,"rate":"36.XX"}`.
