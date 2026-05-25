# Sprint 05 — `parties` + `sales` MVP + S3 adapter + deploy

**Goal.** Complete issuance flow: customer → draft → issuance with 15% VAT → `FOR UPDATE`-locked sequence → stock deduction → downloadable PDF. `FileStorage` port swap: local filesystem ↔ `nica-erp-files` S3 bucket with presigned URL. Closes with an invoice issued at the CloudFront URL and PDF downloaded from S3.

---

## Dependencies

- [00](00-walking-skeleton.md) (`OutboxWriter`); [03](03-tenants-and-rls.md) (RLS); [04](04-catalog-and-inventory.md) (`inventory_writer.consume` wired in `IssueInvoice`).
- **Produced here, consumed later**: `InvoiceIssued` lands in `outbox`; real publisher in [07](07-outbox-eventbridge-audit.md). Meanwhile the in-process dispatcher from sprint 04 delivers it.
- **Tax computation**: this sprint uses `calculate_iva_15` inline (15% VAT uniform, no exemptions). Replaced by the `tax_calculator` port (adapter of the `taxes` context) in [06](06-taxes-payments-reports.md), where IR/IMI/exemptions enter.

---

## `parties/` context

- Aggregates: `Customer`, `Supplier` (separated; distinct flows).
- NI fiscal data: `document_type` (cedula/ruc/ruc_extranjero/passport), `document_number`, `fiscal_address`, `is_withholder` (IR), `is_vat_exempt`.
- Events: `CustomerCreated`, `CustomerUpdated`, `SupplierCreated`, `SupplierUpdated`.

## `sales/` context — MVP

Two aggregate roots coexist in `sales/` because they have independent lifecycles and consistency: `Invoice` changes with every user command, `DgiAuthorization` is administered occasionally and exists without invoices. Linking them into a single root would force unnecessary locks on the authorization on every issuance.

> The `AuthorizationDgi` VO of the `tenants` context ([sprint 03](03-tenants-and-rls.md)) holds the number + validity that the SMB displays on its receipts. The `DgiAuthorization` root here in `sales/` models the **authorized correlative ranges** and groups the derived `NumberSequence`s; distinct names to avoid conceptual collision between contexts.

- **`Invoice`** (root). Sub-entities `InvoiceItem`, `TaxLine`. States `draft → issued → (paid | partially_paid | cancelled)`. Invariants: `issued` does not edit; `cancelled` does not accept payments; no issuance without items. Events: `InvoiceIssued`, `InvoiceCancelled`.
- **`DgiAuthorization`** (root) groups 1:N **`NumberSequence`** (entity): `(authorization_id, document_type, range_from, range_to, next_number, valid_from, valid_to, status)`. Full model in [`../17-compliance-nicaragua.md` #numbersequence](../17-compliance-nicaragua.md#numbersequence).
- `IssueInvoice` resolves the active sequence `(tenant_id, document_type=INVOICE)` and locks `FOR UPDATE` on the `number_sequences` row ([ADR-0008](../adr/0008-for-update-sequence-allocation.md)).
- **`TaxBreakdown`** VO — placeholder with 15% VAT inline.

---

## `IssueInvoice` — critical flow

```python
async def issue_invoice(cmd: IssueInvoiceCommand, uow: UnitOfWork) -> IssueInvoiceResult:
    async with uow.begin() as session:
        # 1. Lock sequence FOR UPDATE
        seq = await number_sequence_repo.get_active_for_update(
            session, tenant_id, document_type=DocumentType.INVOICE
        )
        if seq.is_exhausted:
            raise NumberSequenceExhaustedError()

        # 2. Load invoice draft
        invoice = await invoice_repo.get(session, cmd.invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidInvoiceState()
        if not invoice.items:
            raise InvoiceMustHaveItems()

        # 3. Compute taxes (inline 15% VAT in this sprint)
        # calculate_iva_15 lives in contexts/sales/application/services/tax_calculator_inline.py
        # Sprint 06 replaces it with the outbound TaxCalculator port (adapter of `taxes`).
        tax_breakdown = calculate_iva_15(invoice.items, customer)

        # 4. Assign correlative and issue
        invoice.issue(
            correlativo=seq.next_number,
            tax_breakdown=tax_breakdown,
            issued_at=clock.now(),
        )
        seq.advance()

        # 5. Deduct stock (outbound port to inventory)
        for item in invoice.items:
            await inventory_writer.consume(
                product_id=item.product_id,
                warehouse_id=cmd.warehouse_id,
                quantity=item.quantity,
                reason=f"sale invoice {invoice.correlativo}",
            )

        # 6. Persist + outbox event (same transaction)
        await invoice_repo.save(session, invoice)
        await number_sequence_repo.save(session, seq)
        await outbox.append(
            event_id=uuid4(),
            event_type="sales.InvoiceIssued", event_version=1,
            aggregate_type="Invoice", aggregate_id=invoice.id, tenant_id=tenant_id,
            payload=InvoiceIssued.from_aggregate(invoice).to_dict(),
        )

    return IssueInvoiceResult(invoice_id=invoice.id, correlativo=invoice.correlativo)
```

**Atomicity.** All steps live inside the same `async with uow.begin()`. If any step fails (insufficient stock, exception from the `taxes` adapter tax calculation arriving in [06](06-taxes-payments-reports.md), etc.), Postgres reverts everything — `next_number` does not advance, stock is not deducted, no event enters the outbox. This is the guarantee that justifies outbox over dual-write ([ADR-0006](../adr/0006-transactional-outbox.md)).

`OutboxWriterSqlAlchemy` receives the `AsyncSession` from the active `UnitOfWork` to ensure `invoice`↔`outbox` atomicity.

---

## Use cases

`CreateDraftInvoice`, `UpdateDraftInvoice`, `IssueInvoice`, `CancelInvoice`, `ListInvoices`, `GetInvoice`, `GenerateInvoicePdf`, `RegisterNumberSequence`, `ListNumberSequences`, `CreateCustomer`, `UpdateCustomer`, `DeleteCustomer`, etc.

Endpoints: [`../08-api-conventions.md` #sales](../08-api-conventions.md#sales), [#parties](../08-api-conventions.md#parties).

---

## `InvoicePdfRenderer` + `FileStorage` adapter

- weasyprint in-process (native libs already installed in the Dockerfile from [sprint 01](01-aws-wiring-rolling-deploys.md)). Add to `pyproject.toml`:

  ```toml
  dependencies = [
    # previous +
    "weasyprint>=62,<64", "jinja2>=3.1,<4",
    "openpyxl>=3.1,<4",   # anticipated for XLSX reports of sprint 06
  ]
  ```

- Jinja2 template: SMB header (RUC, address, DGI authorization), customer data, lines, VAT breakdown, **DGI authorization number in the bottom-right corner** (legal requirement).
- `FileStorage` port (`put`, `get`, `presigned_url`):
  - Local: `FileStorageLocal` → `./tmp/files/invoices/<tenant_id>/<invoice_id>.pdf` (no LocalStack).
  - AWS: `FileStorageS3` → `s3://nica-erp-files/invoices/<tenant_id>/<invoice_id>.pdf`.

  To exercise S3 locally: `awslocal s3 mb s3://nica-erp-files` from `docker/localstack-init.sh`.

## Migration 0005

`customers`, `suppliers`, `invoices`, `invoice_items`, `tax_lines`, `dgi_authorizations`, `number_sequences`. Tenant-scoped with RLS (pattern [sprint 03](03-tenants-and-rls.md)). Tables with hybrid ownership (`invoices`, `quotations`) carry `created_by_user_id UUID NOT NULL`. Additional seed in `permissions` + `role_permissions` (see §Permissions below).

---

## Permissions ([ADR-0022](../adr/0022-rbac-model.md))

Added to the catalog:

| Permission | Resources | Default roles |
|---|---|---|
| `customer:read`, `supplier:read` | `Customer`, `Supplier` | all |
| `customer:write`, `supplier:write` | parties catalog | salesperson, accountant, admin, owner |
| `customer:delete`, `supplier:delete` | soft delete | admin, owner |
| `number-sequence:read` | `NumberSequence` | all |
| `number-sequence:write` | activate/deactivate DGI ranges | admin, owner |
| `quotation:read` (own), `quotation:read-all` | `Quotation` | viewer+ (own); accountant+ (all) |
| `quotation:write` | create/edit draft | salesperson+ |
| `quotation:convert` | convert to invoice | salesperson+ |
| `invoice:read` (own), `invoice:read-all` | `Invoice` | viewer+ (own); accountant+ (all) |
| `invoice:write` | create/edit draft | salesperson+ |
| `invoice:issue` | atomic issuance | salesperson+ |
| `invoice:cancel` | cancel `issued` without payments | accountant+ |
| `invoice:send` | email to customer | salesperson+ |
| `credit-note:write`, `credit-note:issue` | credit note | accountant+ |
| `debit-note:write`, `debit-note:issue` | debit note | accountant+ |

`InvoiceRepository` and `QuotationRepository` inherit from `OwnedAggregateRepository` (see [`../06-security-model.md` §Ownership filter](../06-security-model.md#ownership-filter-in-the-query-layer)). Credit/debit notes inherit ownership from the parent `Invoice` — the filter is applied via join (`credit_notes.invoice_id IN (SELECT id FROM invoices WHERE ...)`).

**Sprint gate test**: `pytest -k test_invoice_ownership` — a `salesperson` who creates invoice A must not see invoice B issued by another `salesperson`; an `accountant` sees both.

---

## Frontend

Routes `/parties/{customers,suppliers}[/new|/$id]`, `/sales/invoices[/new|/$id]`, `/sales/number-sequences`. `useIssueInvoice` hook sends `Idempotency-Key`. PDF download: `useDownloadInvoicePdf` (`fetch` + `Blob` + `URL.createObjectURL`). Zod validation: `draftInvoiceSchema` (≥1 line, `quantity > 0`, `unit_price > 0`); `customerSchema` validates `ruc` if `document_type === 'ruc'`. Rest follows README §Shared patterns.

---

## Sprint tests

- Unit: `Invoice.issue()` validates state, assigns correlative, does not allow issuing twice; `NumberSequence.advance()` fails if exhausted.
- Integration: concurrent `IssueInvoice` (two processes issuing at once; lock serializes, no correlative duplication).
- E2E: customer → product → draft → issue → PDF → stock deducted → outbox entry.

---

## Verifiable outcome (local)

```bash
curl -X POST localhost:8000/v1/number-sequences ... \
  -d '{"document_type":"invoice","range_from":1,"range_to":1000,"authorization_number":"...","authorization_date":"2026-01-01"}'
curl -X POST localhost:8000/v1/customers ... -d '{"name":"Distribuidora X","ruc":"...","fiscal_address":"..."}'
INVOICE_ID=$(curl -X POST localhost:8000/v1/invoices ... \
  -d '{"customer_id":"...","items":[{"product_id":"...","quantity":2,"unit_price":25}]}' | jq -r .id)
curl -X POST localhost:8000/v1/invoices/$INVOICE_ID/issue -H "Idempotency-Key: $(uuidgen)" ...
curl localhost:8000/v1/invoices/$INVOICE_ID/pdf -o factura.pdf
```

PDF with correlative, 15% VAT, DGI authorization number. Stock deducted in `/v1/inventory/stock/<product_id>`.

---

## Deploy

Swap `FileStorage` Local→AWS against real S3.

### Terraform additions

- **New `storage/` module**: versioned `nica-erp-files` bucket + SSE-S3, policy allowing the API task `s3:{PutObject,GetObject,DeleteObject}` only on `invoices/<tenant_id>/`. Lifecycle: abort multipart > 7 days.
- **IAM**: role `nica-erp-api-task-role` with S3 over `nica-erp-files`. Presigned URLs TTL 5 min using role credentials.
- **SSM**: `/nica-erp/demo/s3/files_bucket`.
- **Migration 0005**: RLS applied.

### Wiring

```python
def build_file_storage() -> FileStorage:
    if settings.app_env == "local":
        return FileStorageLocal(root=settings.local_files_dir)
    return FileStorageS3(client=boto3.client("s3"), bucket=settings.s3_files_bucket)
```

`GetInvoicePdf` returns `PdfRef` with URL (presigned S3 or local file URL); the frontend downloads from that URL.

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus: issue invoice with 2 items, "Download PDF" → presigned `s3.amazonaws.com` URL, `aws s3 ls s3://nica-erp-files/invoices/<tenant_id>/` lists the object, `stock_levels` reflect the deduction.

**Operational note**: the bucket does not destroy with objects; pre-destroy `aws s3 rm s3://nica-erp-files/ --recursive` (demo PDFs are not real fiscal documents).
