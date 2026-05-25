# 01 — Overview

## Product

Multi-tenant SaaS ERP for small businesses in Nicaragua. **HTTP API** (`apps/api`) + **SPA** (`apps/web`).

First module: **sales, invoicing, and inventory** with DGI compliance:

- **VAT 15%** (general, exempt, zero-rate) per line.
- **IR withholdings**: 2% local purchases on monthly accumulated for the `(withholding customer, supplier)` pair > C$1,000; 10% professional services; others per table.
- Municipal **IMI**: 1% Managua, 0.5–1% others.
- **Sequential numbering** authorized by DGI with depletion alert.
- Monthly **VAT book** exportable to CSV/XLSX.
- **Kardex** by weighted average.
- **PDFs** with authorization number and tax breakdown.

Fiscal detail in [17](17-compliance-nicaragua.md). Endpoints in [08](08-api-conventions.md).

---

## Pre-launch phase

Built to validate with small businesses before operating production tenants. Three pillars:

1. **Clean architecture on a real domain.** Hexagonal + DDD + bounded contexts, `domain ← application ← adapters` validated with `import-linter`. Interchangeable ports (swap `IdentityProviderLocal` ↔ `IdentityProviderCognito` in one line of `bootstrap/container.py`). Multi-tenancy via Postgres RLS. At-least-once outbox. Detail in [02](02-architecture.md).
2. **AWS economy tier.** Minimum tier of each service. CloudFront default as the only front-door ([ADR-0020](adr/0020-no-custom-domain-mvp.md)); secrets in SSM Parameter Store ([ADR-0021](adr/0021-ssm-parameter-store.md)); SES permanent sandbox; no Route 53, no custom ACM, no WAF/X-Ray/Config. 100% Terraform. Detail in [10](10-infrastructure.md).
3. **On/off operability.** Stack destroyed when not in use. `make local-up` (dev), `make deploy/destroy` (sprint session), `make wipe` (full shutdown). Under rolling deploys ([ADR-0018](adr/0018-rolling-deploys.md)) every sprint from [01](sprints/01-aws-wiring-rolling-deploys.md) onward closes deployed. **Idle ~$0/month; running ~2.70 USD/day.**

When the first production tenant arrives, the stack stops being destroyed. Hardening (Multi-AZ, WAF, extended retention) at that point.

---

## Out of scope

- **Own billing layer.**
- No built-in monetization (Stripe, subscription plans) — billing handled outside the product.
- **Automatic deployment CI/CD** ([ADR-0023](adr/0023-no-ci-cd-mvp.md)). GitHub Actions only lint/types/unit tests.
- **Multi-region / multi-account.** One account, `us-east-1`.
- **Real-time electronic invoicing.** Nicaragua does not require it; if it became mandatory, a separate `e-invoicing` context would appear without touching the rest.
- **Strict high availability.** Single-AZ, one NAT. Raised at the first tenant.
- **Premium AWS services** (WAF, X-Ray, VPC Interface endpoints, Config/GuardDuty/Security Hub).

---

## Stack

Only strategic decisions; versions, auxiliary tools, and configuration in [16 — Tooling](16-tooling.md) (backend) and [09 — Frontend](09-frontend.md). AWS operation in [10](10-infrastructure.md).

- **Backend.** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Postgres 16 ([ADR-0010](adr/0010-python-fastapi.md)).
- **Frontend.** React 18 + TS strict + TanStack + shadcn/ui ([ADR-0009](adr/0009-frontend-stack.md)). Generated OpenAPI client.
- **AWS compute.** API on ECS Fargate, hot process ([ADR-0004](adr/0004-ecs-not-lambda.md)). Workers (outbox, audit, notif, fx, housekeeping) on Lambda inside the VPC.
- **Auth.** Cognito User Pool tier Lite in prod; `IdentityProviderLocal` (JWT HS256) in dev — same port ([ADR-0005](adr/0005-cognito-with-local-idp.md)).
- **Events.** At-least-once outbox ([ADR-0006](adr/0006-transactional-outbox.md)) → EventBridge custom bus + SQS + DLQs. Publisher Lambda every 60 s in MVP ([ADR-0007](adr/0007-outbox-dispatch-polling.md)).
- **Frontend hosting.** S3 + CloudFront default in persistent module, independent of the backend lifecycle ([ADR-0020](adr/0020-no-custom-domain-mvp.md)).

---

## Future modules

Each new module enters as a context under `contexts/`, shares `shared_kernel`, communicates via events and outbound ports. Without rewriting existing code. Detailed roadmap in [18](18-roadmap.md) §post-MVP.

| Module | Coverage |
|---|---|
| `purchases` | POs, receipts, supplier invoices, AP, withholding certificates. |
| `accounting` | Chart of accounts, automatic journal entries, books, financial statements. |
| `crm` | Leads, opportunities, pipeline. |
| `hr` | Payroll, INSS, payroll IR. |
| `projects` | Time tracking, budgets. |
| `pos` | Cash register, thermal printing, barcodes. |
