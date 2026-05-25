# 17 — Compliance Nicaragua

> Rates and thresholds are **configuration**. Validate against the Tax Concertation Law, its regulation, and the Municipal Arbitration Plan before operating in production.

---

## DGI framework

DGI (Dirección General de Ingresos) is Nicaragua's tax authority. Nicaragua **does not require real-time electronic invoicing**. The following apply:

- **Technical Disposition 09-2007**: receipts and computerized systems.
- **SACFI** (Sistema de Autorización de Comprobantes Fiscales e Imprentas): authorizes the taxpayer to issue receipts from software. Each small business processes its authorization; it receives an authorization number that must be printed on each receipt with a validity period.

System consequences:

1. Strict sequential numbering by authorized ranges, no gaps or repetitions, with alert before depletion.
2. Regulated types with independent numbering: invoice, receipt (collection), CN, DN, withholding certificate.
3. Mandatory monthly VAT book, fixed format.
4. Exportable backups (CSV/XLSX) for audit.
5. Immutability of issued receipts (invariant of the `Invoice` aggregate — [ADR-0014](adr/0014-soft-delete.md)).

---

## `NumberSequence`

Aggregate of the `sales` context. Fields: `id`, `tenant_id`, `document_type` (invoice/credit_note/debit_note/receipt/withholding), `series` (optional, branch), `range_from`, `range_to`, `next_number`, `authorization_number`, `authorization_date`, `expires_at`, `is_active`, `low_threshold_pct`.

**Rules**:

- Only one active per `(tenant_id, document_type, series)`.
- Issuance: `SELECT ... FOR UPDATE` on the active one, assigns `next_number`, increments, commit ([ADR-0008](adr/0008-for-update-sequence-allocation.md)).
- `next_number > range_to` → range exhausted (business error).
- `(next_number - range_from) / (range_to - range_from + 1) >= low_threshold_pct/100` → publishes `NumberSequenceLowAlerted` (consumed by `notifications`).
- `POST /v1/number-sequences` for a new range; activating it deactivates the previous.

Why not Postgres `SEQUENCE`: it is global, not reused on failure, does not support external authorized ranges.

---

## Taxes

All calculation is done by `taxes` via `TaxCalculator` (outbound port from `sales` and future `purchases`).

### IVA (VAT) — 15%

IVA (Impuesto al Valor Agregado) — Nicaragua's value-added tax. General 15% / exempt 0% (basic basket, health, education) / zero-rate (exports). Type by product; exemption by customer (international organizations, government under conditions). Effective rule per line = intersection. Breakdown per line + total.

### IR withholdings

IR (Impuesto sobre la Renta) — Nicaragua's income tax. Applies if `Customer.is_retainer = true`. Rates (verify currency):

| Concept | Rate | Notes |
|---|---|---|
| Local purchases | 2% | C$1,000 monthly accumulated threshold per `(withholder, supplier)` pair — exceeding the threshold → **all** invoices of the pair for the month withhold |
| Professional services | 10% | consulting, accountants, lawyers |
| Technical services | 3% | |
| Non-residents without treaty | 30% | with treaty per country rate |
| Rentals | 15% | when applicable |

The withheld IR **is subtracted from the total to charge** (the customer remits it to DGI). It appears as "IR withheld" on the receipt.

### IMI — Municipal Tax on Income

IMI (Impuesto Municipal sobre Ingresos). 1% Managua, 0.5–1% other municipalities. **Seller's cost, not passed through.** Monthly settlement on gross income; broken down per invoice for audit (`/v1/reports/imi`) but does not appear on the physical receipt.

### `TaxCalculator`

`calculate_for_sale(tenant_id, lines, customer, emission_date) -> TaxBreakdown`. Analogous `calculate_for_purchase`. `TaxBreakdown` (immutable VO): `lines[TaxLine]`, `vat_total`, `ir_withheld_total`, `imi_total` (informational), `total_after_taxes`, `total_to_charge = total_after_taxes - ir_withheld_total`. Reads `tenants.tax_config` (jsonb).

---

## VAT book

`GET /v1/reports/vat-book?month=YYYY-MM` (`format=json|csv|xlsx`). XLSX with DGI template. One row per receipt: date, type, number, RUC/cédula, name, net value, VAT 15%, VAT exempt, total. Summation at the end.

---

## Withholding certificates

When the small business withholds from a supplier, it issues a monthly Certificate (Constancia de Retención). Belongs to the `purchases` context (post-MVP). `NumberSequence` already supports the type.

---

## MVP coverage

**Included**: VAT 15% general/exempt/zero-rate, IR withholdings (multiple rates), informational IMI, sequential numbering, monthly VAT book, PDF with authorization, CN/DN.

**Out of MVP**:

- Issued withholding certificates (`purchases` module, sprints 15–17 of the [roadmap](18-roadmap.md#post-mvp-roadmap)).
- DGI annexes for large taxpayers: partial modeling (fields in `tax_withholdings`); the official report requires a specific format not built in MVP.
- Non-resident rates per country with treaty: the code supports the general 30% (placeholder); reduced rates per bilateral treaty require modeling country/concept pair and are not included.
- INSS / payroll IR (`hr` module, sprint 20).
- DGI electronic invoicing: not applicable in Nicaragua (SACFI does not require it).
