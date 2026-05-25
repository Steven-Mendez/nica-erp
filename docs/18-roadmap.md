# 18 — Roadmap

The MVP is structured as 10 sprints (00–09) under rolling deploys ([ADR-0018](adr/0018-rolling-deploys.md)). Every sprint delivers one vertical slice — a bounded context plus the AWS adapter for the new outbound port the slice introduces — and closes deployed against the public stack. Canonical Definition of Done, the post-deploy verification protocol, and the port↔adapter table live in [`sprints/README.md`](sprints/README.md); the entries below are one-line goals, not duplicates.

The old MVP plan was 11 sprints (00–10); sprints 00 and 01 were merged and the old hardening sprint 10 folded into sprint 09 ([ADR-0018](adr/0018-rolling-deploys.md)).

---

## MVP roadmap (sprints 00–09)

| # | Goal |
|---|---|
| [00](sprints/00-walking-skeleton.md) | Monorepo `apps/api` + `apps/web`, walking skeleton (`/healthz`), `shared_kernel`, Postgres, Alembic 0001. Local only. |
| [01](sprints/01-aws-wiring-rolling-deploys.md) | Terraform bootstrap + first `make deploy`; SPA + API on CloudFront default. `make deploy/destroy` part of DoD from here on. |
| [02](sprints/02-identity-and-rbac.md) | Signup/login/`/me` against local IdP and real Cognito; permission catalog seeded. |
| [03](sprints/03-tenants-and-rls.md) | Multi-tenancy with RLS; two tenants isolated, verified in AWS. |
| [04](sprints/04-catalog-and-inventory.md) | `catalog` + `inventory` with kardex valued at weighted average. |
| [05](sprints/05-parties-and-sales.md) | Invoice issuance with VAT, `FOR UPDATE` sequence, PDF in real S3. |
| [06](sprints/06-taxes-payments-reports.md) | `taxes` (IR/IMI), `payments`, VAT book, BCN scraper Lambda. N+1 gate on monthly IR accumulation. |
| [07](sprints/07-outbox-eventbridge-audit.md) | Outbox publisher Lambda + EventBridge + `audit_consumer` + audit ledger. |
| [08](sprints/08-notifications-ses.md) | `notifications_worker` Lambda + SES sandbox + Jinja2 templates. |
| [09](sprints/09-mvp-validation.md) | Contract tests parametrized, cost audit, walkthrough video. Absorbs the old hardening sprint. |

---

## MVP cycle cost

- **Idle ~$0/month** ([ADR-0020](adr/0020-no-custom-domain-mvp.md), [ADR-0021](adr/0021-ssm-parameter-store.md)).
- **Running ~$2.70 USD/day**; ~$3 per same-day verification session, ~$8 for a 3-day session.
- **9 sprints with deploy** × 1–3 cycles ≈ **$25–50 USD** across the entire MVP.

Deploy/destroy policy in [ADR-0003](adr/0003-deploy-destroy-per-env.md); per-component breakdown in [10 §Cost](10-infrastructure.md); cycle cost in [11 §Cycle cost](11-deployment.md#cycle-cost).

---

## Post-MVP (out of scope for current build)

Numbering is provisional. Sprints 10–13 are prerequisites for a real productive tenant; sprint 14+ extend the domain.

| Sprint | Theme | Detail |
|---|---|---|
| 10 | Observability expansion | CloudWatch Insights queries, EMF dashboards, SLO alerts. Evaluate OpenTelemetry → X-Ray. |
| 11 | Security hardening | OWASP Top 10, WAF managed + rate-based, security review of critical domain, RDS managed rotation. |
| 12 | Performance testing | k6 against critical endpoints, `EXPLAIN (ANALYZE, BUFFERS)`, missing indexes. |
| 13 | User documentation | Manual, troubleshooting, full walkthrough video. |
| 14–16 | `purchases` | PO, receipts, supplier invoices, AP, withholding receipts (closes the gap in [17](17-compliance-nicaragua.md)). |
| 17–18 | `accounting` | Chart of accounts, journal entries from events, ledgers, basic financials. |
| 19 | `hr` | Employees, payroll, INSS, payroll IR. |
| 20 | `crm` | Leads, opportunities, pipeline. |
| 21 | `pos` | Register, thermal printing, barcodes. |
| 22 | `projects` | Time tracking, budgets. |
