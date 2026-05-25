# 19 — Glossary

NI fiscal, DDD, AWS, Postgres, and project terms referenced in the docs.

---

## Fiscal Nicaragua

Fiscal terms keep their Spanish names as proper nouns (DGI, IR, IVA, IMI, RUC); the Spanish ↔ English column doubles as a translation reference for working with Nicaraguan sources.

| Term | Spanish ↔ English | Definition |
|---|---|---|
| **DGI** | Dirección General de Ingresos / General Directorate of Revenue | Nicaragua's tax authority. |
| **RUC** | Registro Único del Contribuyente / Unique Taxpayer Registry | 14 digits. |
| **Cédula** | Cédula de identidad / National ID card | Personal NI identity document. 14 characters: 13 digits + 1 letter (`###-######-####X`). |
| **IVA** | Impuesto al Valor Agregado / Value-Added Tax (VAT) | 15% general. Exempt (basic basket, health, education) and zero-rate (exports). |
| **IR** | Impuesto sobre la Renta / Income Tax | The system models **withholdings at source**: 2% local purchases with monthly accumulated > C$1,000, 10% professional services, 3% technical services, 30% non-residents without treaty, 15% rentals. |
| **IMI** | Impuesto Municipal sobre Ingresos / Municipal Tax on Income | 1% Managua, 0.5–1% others. Seller's cost, not passed through. |
| **Retenedor** | Retenedor / Withholding agent | Customer classified as IR withholding agent. Withholds the IR on the invoice (subtracts from the total to charge) and remits it to DGI. Per-customer flag; C$1,000 monthly threshold applies per `(withholder, supplier)` pair. See [17 § IR](17-compliance-nicaragua.md#ir-withholdings). |
| **Factura** | Factura / Invoice | Sales receipt subject to sequential numbering and DGI authorization. |
| **Recibo** | Recibo / Receipt | Collection receipt; independent numbering from the invoice. |
| **Nota de crédito (NC)** | Nota de crédito / Credit note (CN) | Inverse rectification document. |
| **Nota de débito (ND)** | Nota de débito / Debit note (DN) | Additional charge document. |
| **Retención** | Retención / Withholding | Amount withheld at source by the withholder. |
| **Constancia de Retención** | Constancia de Retención / Withholding certificate | Monthly receipt that the withholder issues to the supplier. Separate DGI type. Belongs to the `purchases` module (post-MVP). |
| **Proveedor** | Proveedor / Supplier | Counterparty on the purchases side. |
| **Cliente** | Cliente / Customer | Counterparty on the sales side. |
| **Comprobante** | Comprobante / Receipt-document | Generic term for tax-regulated document (invoice, CN, DN, receipt, certificate). |
| **SACFI** | Sistema de Autorización de Comprobantes Fiscales e Imprentas / Fiscal Receipts and Printers Authorization System | DGI portal where the small business requests the sequential numbering range. DGI authorizes in 2–7 business days. |
| **Disposición Técnica 09-2007** | Technical Disposition 09-2007 | DGI regulation on receipt issuance and computerized systems. |
| **Numeración correlativa** | Numeración correlativa / Sequential numbering | Consecutive series authorized by DGI per document type. No gaps or repetitions. Guaranteed with `FOR UPDATE` on `number_sequences` ([ADR-0008](adr/0008-for-update-sequence-allocation.md)). |
| **Libro de IVA** | Libro de IVA / VAT book | Mandatory monthly report: one row per receipt with date, type, number, RUC/cédula, name, net value, VAT 15%, VAT exempt, total + summation. CSV/XLSX. |
| **Kardex** | Kardex | Chronological record of inventory movements with cumulative balance. Valued by **moving weighted average** ([ADR-0019](adr/0019-kardex-inventory.md)). |
| **Anexos DGI** | Anexos DGI / DGI Annexes | Complementary forms to the VAT book and annual return. MVP covers the basics. |

---

## Authorization

| Term | Definition |
|---|---|
| **Granular RBAC** | Authorization model adopted in nica-erp: 5 fixed roles × ~60 `<resource>:<action>` permissions. Mapping in `role_permissions`, source of truth in `shared_kernel/permissions/catalog.py` ([ADR-0022](adr/0022-rbac-model.md)). |
| **Permission code** | Stable string `<resource>:<action>[-all]`. Examples: `invoice:issue`, `invoice:read-all`, `tax-config:write`. Row in `permissions(code PK)`. |
| **Hybrid ownership** | Pattern where a resource with a natural owner (`Invoice.created_by_user_id`, etc.) declares `*:read` (visible only if actor = owner) and `*:read-all` (bypass). Filter applied in the query layer (`OwnedAggregateRepository`). See [06 §Authorization](06-security-model.md#authorization). |
| **`Actor`** | In-memory DTO per request: `(user_id, tenant_id, role, permissions: frozenset[str])`. Resolved by the `current_actor` dependency. |
| **`require(*codes)`** | FastAPI dependency that validates that the actor has the listed permissions; fails with `ForbiddenError` → 403 `type=missing-permission`. |
| **MVP roles** | `viewer` < `salesperson` < `accountant` < `admin` < `owner`. **Not** strict hierarchy: each role is explicitly assigned its permission set in `DEFAULT_ROLE_PERMISSIONS`. `owner` unique per tenant (`UNIQUE (tenant_id) WHERE role='owner'`). |

---

## DDD

| Term | Definition |
|---|---|
| **Bounded Context** | Boundary where a model has meaning. 11 in nica-erp: `identity`, `tenants`, `catalog`, `inventory`, `parties`, `sales`, `taxes`, `payments`, `reports`, `notifications`, `audit`. Map in [03](03-bounded-contexts.md). |
| **Aggregate** | Cluster of entities + VOs treated as a unit; the root controls modifications to maintain invariants. E.g., `Invoice` with its `InvoiceItem` and `TaxLine`. |
| **Value Object** | Immutable object identified by its value. E.g., `Money`, `Email`, `Sku`, `Ruc`, `TaxBreakdown`. |
| **Domain Event** | Significant event within an aggregate. Lives in-process. |
| **Integration Event** | Event that crosses contexts via external bus (EventBridge). Persisted in `outbox` in the same transaction as the command ([07](07-events-and-outbox.md)). |
| **Port (inbound / outbound)** | Interface of what a context **offers** (inbound = use cases) or **needs** (outbound = repos, lookups, publishers). |
| **Adapter** | Concrete implementation of a port against a technology (SQLA, Cognito, SES, EventBridge…). |
| **Use Case / Application Service** | Class that orchestrates a flow (`CreateInvoiceUseCase`). Validates cross-context invariants via outbound ports and persists with UoW. Has no domain rules. |
| **CQRS (pragmatic)** | Commands via aggregates; queries read tables directly. Used in reports and in `customer_lookup` / `product_lookup`. |
| **Outbox pattern** | Persist the event as a row in the same transaction as the command; separate asynchronous publisher. At-least-once. MVP trigger: 60 s Scheduler; `LISTEN/NOTIFY` post-MVP ([ADR-0007](adr/0007-outbox-dispatch-polling.md)). |

---

## AWS / Infrastructure

| Term | Definition |
|---|---|
| **VPC** | Virtual Private Cloud. nica-erp: `10.0.0.0/16`, pub/priv subnets in 2 AZ. |
| **AZ** | Availability Zone. Data center within a region. |
| **ALB** | Application Load Balancer. Layer 7. Under [ADR-0020](adr/0020-no-custom-domain-mvp.md), nica-erp uses it **HTTP-only :80** restricted to the prefix list `com.amazonaws.global.cloudfront.origin-facing`; TLS terminates at CloudFront. |
| **NAT Gateway** | Egress for private subnets. Component with the highest hourly cost if `make destroy` is forgotten (~1.15 USD/day). |
| **WAF** | Web Application Firewall. Excluded by cost in MVP. |
| **ACM** | AWS Certificate Manager. Pre-launch nica-erp **does not** issue a custom cert; CloudFront uses the default cert managed by AWS. |
| **RDS** | Managed Postgres. `db.t4g.micro` single-AZ + gp3 20 GB. |
| **`db.t4g.micro`** | ARM Graviton instance, t4g micro: 2 vCPU burst, 1 GB RAM. |
| **RDS Proxy** | Pooler between consumers and RDS. Irrelevant with Fargate; useful with Lambdas fan-out. [ADR-0004](adr/0004-ecs-not-lambda.md). |
| **ECS Fargate** | Managed containers without EC2. API at `0.25 vCPU / 0.5 GB`. |
| **ECR** | Private container registry. One multi-purpose image (API + workers). |
| **EventBridge** | Event bus. Custom bus `pyme-erp` with rules to SQS. |
| **SQS** | Standard/FIFO queues. Each Lambda consumer has its queue and DLQ. |
| **DLQ** | Dead-letter queue. SQS uses it after `maxReceiveCount=5`. Alarm when there are messages. |
| **SES** | Transactional email. Pre-launch nica-erp operates in **permanent sandbox** with email-only verification ([ADR-0020](adr/0020-no-custom-domain-mvp.md)). |
| **Cognito** | Managed User Pool. nica-erp uses **tier Lite** without Hosted UI ([ADR-0005](adr/0005-cognito-with-local-idp.md); verify active MAU cap in [pricing](https://aws.amazon.com/cognito/pricing/)). |
| **MAU** | Monthly Active User. Cognito billing metric. |
| **JWKS** | JSON Web Key Set. Public keys that sign the IdP's JWTs. Cached 24 h in task memory. |
| **OAC** | Origin Access Control. CloudFront → private S3 access. Replaces the old OAI. |
| **SSM Parameter Store** | Config store and, under [ADR-0021](adr/0021-ssm-parameter-store.md), also of the 3 persistent secrets (`db/master`, `jwt/signing-key`, `integrations/*`) as `SecureString` with `aws/ssm`. |
| **Secrets Manager** | Alternative to SSM with optional rotation (~0.40 USD/secret/month). **Not used** pre-launch ([ADR-0021](adr/0021-ssm-parameter-store.md)). |
| **X-Ray** | Distributed tracing. **Not used** due to cost. Traceability via `correlation_id` in Logs Insights. |
| **EMF** | Embedded Metric Format. CloudWatch publishes metrics from log lines without an extra API. |
| **LocalStack** | AWS emulator in Docker. nica-erp uses community with S3, SQS, EventBridge, SSM. Cognito and Lambda are not in community. |
| **Mailpit** | Dummy SMTP server with UI `http://localhost:8025`. `EmailSenderSmtp` adapter in dev. |
| **`IdentityProviderLocal`** | Dev adapter of the `IdentityProvider` port. JWT HS256, users in `auth_local_users` (citext). Replaces Cognito locally. |
| **pre-commit** | Hook framework (`.pre-commit-config.yaml`). See [16](16-tooling.md). |
| **CloudFront** | AWS CDN. Under [ADR-0020](adr/0020-no-custom-domain-mvp.md) it is the **only HTTPS front-door** via `https://<dist-id>.cloudfront.net/` with two behaviors: `/*` → S3 `pyme-erp-web`, `/api/*` → ALB (HTTP-only, no cache). |

---

## Postgres / Data

| Term | Definition |
|---|---|
| **RLS** | Row-Level Security. Filters rows per a policy. Multi-tenant isolation mechanism ([05](05-multi-tenancy.md), [ADR-0002](adr/0002-postgres-rls.md)). |
| **`SET LOCAL`** | Session variable valid only for the current transaction. Discarded on commit/rollback. nica-erp sets `app.tenant_id` and `app.current_user_id` this way per request. |
| **`FOR UPDATE`** | Pessimistic lock until commit/rollback. Used on `number_sequences` for sequential numbers without gaps ([ADR-0008](adr/0008-for-update-sequence-allocation.md)). |
| **`LISTEN/NOTIFY`** | Native Postgres pub/sub. **Not used** in MVP; the publisher runs via 60 s Scheduler ([ADR-0007](adr/0007-outbox-dispatch-polling.md)). |
| **`BYPASSRLS`** | Role attribute that ignores RLS policies. Reserved for privileged roles; in MVP the publisher reads `outbox` (table without RLS enabled) without requiring it. |
| **UUIDv7** | Time-ordered UUID (first 48 bits = timestamp). Allows chronological ordering. Used for `event_id` and aggregate PKs ([ADR-0011](adr/0011-uuidv7-identifiers.md)). |
| **JSONB** | Binary JSON type. Indexable (GIN). Used in `outbox.payload`, `tenants.tax_config`, `users.preferences`, `idempotency_keys.response_body`. |

---

## Project

| Term | Definition |
|---|---|
| **`make local-up`** | Docker Compose up: Postgres + LocalStack + Mailpit. |
| **`make deploy`** | Build + push ECR + `terraform apply` + migrate + print URLs. ~12 min. |
| **`make destroy`** | `terraform destroy` of the ephemeral environment. ~10 min. Preserves 3 categories (state, lock, ECR + S3 web, and CloudFront from bootstrap, both free tier). Pre-launch the DB **is lost** ([ADR-0017](adr/0017-backups-pitr.md)). No Route 53 or Secrets Manager ([ADR-0020](adr/0020-no-custom-domain-mvp.md), [ADR-0021](adr/0021-ssm-parameter-store.md)). |
| **`make destroy-bootstrap`** | Destroys bootstrap resources (irreversible). Requires typing `DESTROY BOOTSTRAP`. Detail in [11 § Total destruction](11-deployment.md#total-destruction-make-wipe). |
| **`make wipe`** | `make destroy && make destroy-bootstrap`. Full shutdown. Idle at $0/month. |
| **Sprint** | Roadmap unit. 10 sprints (00–09) under rolling deploys ([ADR-0018](adr/0018-rolling-deploys.md)). Detail in [`sprints/`](sprints/). |
| **Project naming** | Three coexisting forms by convention: **`nica-erp`** public (GitHub repo, branding); **`pyme_erp`** Python package (legacy of the original internal name); **`pyme-erp`** AWS resource prefix (`pyme-erp-api`, `pyme-erp-files`, `/pyme-erp/db/master`, `pyme-erp.auth.us-east-1.amazoncognito.com`). Migrating the AWS prefix to `nica-erp` requires `make wipe` + new bootstrap; not planned. |
| **ADR** | Architecture Decision Record. Decisions in [`adr/`](adr/README.md). |
| **`bootstrap/container.py`** | Single place that wires concrete adapters to ports. Where `IdentityProviderLocal` vs `IdentityProviderCognito`, etc. is chosen. |
| **`shared_kernel`** | Cross-cutting code (`AggregateRoot`, `Entity`, `ValueObject`, `DomainEvent`, `Money`, `UnitOfWork`, `OutboxWriter`). No business logic. |
| **TanStack** | TS-first family: Router, Query, Table, Form. Typed, headless. |
| **shadcn/ui** | React components over Radix + Tailwind, copied into the repo at `apps/web/src/components/ui/`. |
