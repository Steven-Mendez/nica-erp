# 05 — Multi-tenancy

**Pool + Postgres RLS.** One database, a `tenant_id NOT NULL` column on every tenant-scoped table, RLS as defense in depth. Comparison with Silo/Bridge in [ADR-0002](adr/0002-postgres-rls.md).

---

## Implementation

### Schema

Every tenant-scoped table carries an indexed `tenant_id UUID NOT NULL`, with an RLS policy that filters by the `app.tenant_id` GUC. `FORCE ROW LEVEL SECURITY` ensures the policy also applies to the table owner.

```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON invoices
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

Without RLS, a forgotten `WHERE tenant_id = …` leaks data. Without the index, RLS wrecks the query plan.

### Per-request GUCs

Two GUCs `SET LOCAL` per transaction:

| GUC | Source | RLS use |
|---|---|---|
| `app.tenant_id` | `custom:active_tenant` claim on the JWT | tenant filter on tenant-scoped tables |
| `app.current_user_id` | `sub` from the JWT resolved to `users.id` | global tables that depend on the user (e.g. `tenant_members_self`) |

`current_setting(..., true)::uuid` returns `NULL` when unset (allows bootstrap and migrations). Policies that combine both use `OR`.

### Middleware

`uow.begin()` opens the transaction → `SET LOCAL app.tenant_id` and `SET LOCAL app.current_user_id` **before** any query → use case → `COMMIT`/`ROLLBACK` discards the GUCs.

`SET LOCAL` is transaction-scoped, not session-scoped: **zero leak between requests** sharing a pool connection. If an endpoint forgets `uow.begin()`, RLS returns zero rows for every tenant (the canonical signal of the bug). Gate test in [sprint 03](sprints/03-tenants-and-rls.md).

### `TenantContext` (ContextVar)

`shared_kernel/adapters/`: `current_tenant: ContextVar[UUID | None]`. Use cases and queries read it from the ContextVar rather than receive it as a parameter.

### Global tables without RLS

| Table | Reason |
|---|---|
| `users` | Identity crosses tenants. |
| `tenants` | Catalog itself. |
| `units_of_measure` | Global catalog. |
| `permissions`, `role_permissions` | System catalog, not per-tenant ([ADR-0022](adr/0022-rbac-model.md)). |
| `outbox`, `processed_events`, `idempotency_keys` | Cross-tenant by design; `tenant_id` is only a filter column. The publisher is a system process (DB role without `BYPASSRLS` but operating on tables with RLS disabled). |

`audit_log_entries` **does carry standard RLS by `tenant_id`** — it is read by tenant admins, not the publisher — so the `audit` consumer writes with `SET LOCAL app.tenant_id` extracted from the event. Canonical pattern in [sprint 07 §audit](sprints/07-outbox-eventbridge-audit.md).

### Tables with special-case RLS

| Table | Policy |
|---|---|
| `tenant_members` | `USING (user_id = current_user_id OR tenant_id = current_tenant)` so a user can read their memberships without an active tenant (see [sprint 03](sprints/03-tenants-and-rls.md)). |

### Mitigated risks

- **PgBouncer transaction mode**: `SET LOCAL` clears at COMMIT/ROLLBACK; never persists.
- **Admin scripts**: dedicated role without `BYPASSRLS`, explicit `SET LOCAL`.
- **Cross-tenant outbox**: intentional; the publisher routes to the bus, never exposes data to user APIs.
- **Alembic migrations**: owner role, no per-tenant data routing.

---

## End-to-end flow

```mermaid
sequenceDiagram
    participant Cli as Client
    participant MW as Middleware
    participant DB as Postgres
    Cli->>MW: GET /v1/invoices (Bearer JWT)
    MW->>MW: validate JWT, extract sub + custom:active_tenant
    MW->>DB: BEGIN; SET LOCAL app.tenant_id, app.current_user_id
    MW->>DB: SELECT * FROM invoices WHERE ...
    Note over DB: RLS injects tenant_id = $current_setting
    DB->>Cli: only rows from the active tenant
    MW->>DB: COMMIT (discards SET LOCAL)
```

---

## Special cases

- **Tenant switch**: `POST /v1/tenants/{id}/switch` validates membership, calls `AdminUpdateUserAttributes` (or the local equivalent), returns fresh tokens.
- **Public invitations**: `POST /v1/invitations/{token}/accept` runs without `SET LOCAL app.tenant_id` (access limited to global tables).
- **Owner cross-tenant reports**: out of MVP. If needed later, a separate DB role with `BYPASSRLS` plus a specific claim.

---

## Capacity and scalability

Pool on a single instance works for tens of tenants. Signal → action → where to change it:

| Signal | Action | Where |
|---|---|---|
| ≥ 5 sustained Fargate tasks (each task `pool_size=5 + max_overflow=10` = 15 conn; `db.t4g.micro` `max_connections ≈ 87`) | Lower `pool_size` or scale the RDS instance | `bootstrap/settings.py` (`pool_size`) or `terraform.tfvars` (`rds_instance_class`) |
| Connections exhausted with N tasks or multiple Lambdas hitting RDS | Enable **RDS Proxy** | `data/` module (`enable_rds_proxy = true`). Detail in [10 § Capacity](10-infrastructure.md#capacity-and-scalability) |
| Reports weigh on the primary (monthly VAT book, aggregate kardex) | Read replica dedicated to `reports` (the `*_queries` port is already split from the UoW) | `data/` module (`enable_read_replica = true`) + wiring in `bootstrap/container.py` |
| `audit_log_entries` > ~10M rows on one tenant | Native partitioning by month on `occurred_at` | Alembic migration, no application changes |
| Tens of tenants with heterogeneous loads | Evaluate **Aurora Serverless v2**, or jump to **Bridge** (one schema per tenant) only for tenants that justify it | new ADR |

**None of these requires rewriting application logic.**

---

## Tenant lifecycle

State lives in `tenants.status`. Four states, three irreversible transitions. Each transition emits an integration event via the outbox ([ADR-0006](adr/0006-transactional-outbox.md)). Full rationale, alternatives, and operator runbooks in [ADR-0026](adr/0026-tenant-lifecycle.md); summary below.

```
provisioning ──► active ──► suspended ──► purged
                   ▲           │
                   └───────────┘
```

| State | Meaning | What works | What doesn't |
|---|---|---|---|
| `provisioning` | Signup in progress (Cognito user created, RLS schema not yet seeded) | Signup callback endpoints | API; user sees "we're getting your workspace ready" |
| `active` | Default operating state | Everything | — |
| `suspended` | Non-payment, abuse, or owner request | Read-only API; no event publishing; no UI mutation | Mutations return 403 `problem+json` type `tenant-suspended` |
| `purged` | Fiscal retention window expired and owner requested deletion | Nothing | Tenant ID 410 Gone; data hard-deleted |

### Transitions

| From | To | Driver | Trigger | Side effects |
|---|---|---|---|---|
| (none) | `provisioning` | self-signup | `POST /v1/auth/register` succeeds | `TenantProvisioning` event |
| `provisioning` | `active` | system | Cognito email verified + RLS schema seeded | `TenantActivated` event; first admin user role granted |
| `active` | `suspended` | super-admin (manual) | runbook in [`13-operations.md`](13-operations.md) | `TenantSuspended` event; sessions revoked on next refresh |
| `suspended` | `active` | super-admin (manual) | runbook | `TenantReactivated` event |
| `suspended` | `purged` | super-admin + owner consent | runbook; only after the fiscal retention window (5 years per DGI, per [ADR-0017](adr/0017-backups-pitr.md)) | `TenantPurged` event; data hard-deleted in a batched transaction; backup snapshots retained under `retention/legal-hold/` |

### Hard constraints

- **Fiscal data is never deleted while inside the retention window.** A purge before year 5 requires an explicit legal-hold override and is logged.
- **`active → purged` is forbidden.** Suspension is a mandatory cooling-off step.
- **`purged → *` is irreversible.** Recovery is from backup snapshot only and requires a new tenant ID.
- **Session revocation on suspend** is best-effort — JWTs remain valid until natural expiry (≤ 1 hour, per [06 — Security model § TTLs](06-security-model.md#ttls)). The backend additionally checks `tenants.status` on every authenticated request via the same dependency that loads the tenant context.
