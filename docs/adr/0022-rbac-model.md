# ADR-0022 — Authorization: RBAC with granular permissions and hybrid ownership

**Status**: Accepted
**Date**: 2026-05-23

## Context
[ADR-0002](0002-postgres-rls.md) solves isolation **between** tenants via RLS, but not authorization **within** a tenant. Sprint 03 declares five roles (`owner`, `admin`, `accountant`, `salesperson`, `viewer`) without defining what each can do. Sprint 05 introduces the first endpoint where a `viewer` clearly should not issue an invoice, so the model has to be defined before then — otherwise retroactive gating is needed.

Constraints: a single person codes ([ADR-0018](0018-rolling-deploys.md)); SMEs with small headcount; the real need for a salesperson to see **their** invoices but not those of another salesperson in the same tenant, while the accountant and owner see everything.

## Decision
**Five fixed roles** (not editable by the tenant in MVP) + **granular permission catalog** versioned in code + **hybrid ownership** per visible resource.

### Tables

```sql
CREATE TABLE permissions (
  code         TEXT PRIMARY KEY,                 -- e.g. 'invoice:issue', 'invoice:read-all'
  resource     TEXT NOT NULL,                    -- 'invoice'
  action       TEXT NOT NULL,                    -- 'issue', 'read', 'read-all', 'write', 'delete', ...
  scope        TEXT NOT NULL,                    -- 'own' | 'all' | 'na' (when ownership does not apply)
  description  TEXT NOT NULL
);

CREATE TABLE role_permissions (
  role        TEXT NOT NULL,                     -- 'viewer' | 'salesperson' | 'accountant' | 'admin' | 'owner'
  permission  TEXT NOT NULL REFERENCES permissions(code),
  PRIMARY KEY (role, permission)
);
```

Both are **global without RLS** (system catalog, not per-tenant). Initial seed in an Alembic migration; each sprint that introduces a context adds `INSERT INTO permissions ... ON CONFLICT DO NOTHING` and the default `role_permissions` in its migration. The source of truth for the catalog is Python code (`shared_kernel/permissions/catalog.py`) — the migration mirrors it.

### Naming convention

`<resource>:<action>` with optional suffixes `-all` (hybrid ownership) and `-own` when explicit differentiation is needed. Examples: `invoice:read` (own), `invoice:read-all` (all in the tenant), `invoice:issue`, `invoice:cancel`, `tax-config:write`.

### Hybrid ownership

Resources with a natural owner (`Invoice.created_by_user_id`, `Quotation.created_by_user_id`, `CustomerPayment.recorded_by_user_id`, `Notification.user_id`) declare two permissions:

- `<resource>:read` — visible only if `resource.<owner_col> = current_user_id` or if the ContextVar `current_user_permissions` includes `<resource>:read-all`.
- `<resource>:read-all` — bypasses the ownership filter.

The filter is applied in the context repository (query layer), not in the use case. If the actor has `*:read-all`, the query does not add `WHERE created_by = ...`. Resources without a natural owner (`Product`, `Warehouse`, `TaxConfig`, `AuditLogEntry`, `NumberSequence`) only declare `*:read` with `scope='na'`.

### Enforcement

FastAPI dependency on the router:

```python
def require(*permissions: str) -> Callable:
    async def _check(actor: Actor = Depends(current_actor)) -> Actor:
        missing = [p for p in permissions if p not in actor.permissions]
        if missing:
            raise ForbiddenError(missing=missing)
        return actor
    return _check

@router.post("/v1/invoices/{id}/issue")
async def issue_invoice(id: UUID, _: Actor = Depends(require("invoice:issue"))):
    ...
```

`current_actor` resolves `(user_id, tenant_id, role, permissions_set)` per request. `permissions_set` is loaded **once per request** from an in-process TTL-60s cache `(role -> frozenset[permission_code])` — mappings only change on migration or reseed. The dependency goes in the endpoint signature, **not** in global middleware, so OpenAPI documents the permissions in `description`.

### Defaults per role (summary)

| Role | Philosophy |
|---|---|
| `viewer` | Read-only over its own (`*:read`) + non-fiscal operational reports. |
| `salesperson` | viewer + create/edit drafts + issue invoice + receive payments. Sees only own documents. |
| `accountant` | salesperson + `*:read-all` (all in the tenant) + CN/DN + VAT book + withholdings + IMI + apply/reverse payments. |
| `admin` | accountant + administration (catalog, inventory, tax-config, number-sequences, members, audit-log). |
| `owner` | admin + transfer ownership + (post-MVP) delete tenant. Unique per tenant (`UNIQUE (tenant_id) WHERE role='owner'`). |

Full permission catalog and per-role mapping in [06-security-model.md §Authorization](../06-security-model.md#authorization). Each sprint with a new context adds its "Permissions" section following the canonical table in doc 06 (e.g., [sprint 03 §Granular RBAC](../sprints/03-tenants-and-rls.md#granular-rbac--catalog-and-enforcement), [sprint 04 §Permissions](../sprints/04-catalog-and-inventory.md#permissions-adr-0022), [sprint 05 §Permissions](../sprints/05-parties-and-sales.md#permissions-adr-0022)).

### Errors

`ForbiddenError` maps to `403` Problem Details `type=missing-permission`, extension `missing: ["invoice:issue"]` ([ADR-0015](0015-rfc7807-errors.md)). 404 is reserved for "does not exist in this tenant"; 403 for "exists but you can't". Ambiguity (filter 403→404 to avoid enumeration) is evaluated post-MVP.

### Out of MVP

- Tenant-editable custom roles.
- Per-instance permissions (resource ACLs, e.g., "this salesperson can void this specific invoice").
- Temporary delegation.
- Permissions admin UI (defaults are edited via migration).

## Consequences
- (+) Every endpoint declares its explicit permission; OpenAPI exposes it; tests can sweep the whole matrix.
- (+) Hybrid ownership covers the real SME case ("salesperson sees own, accountant sees all") without escalating the role.
- (+) Default changes = Alembic migration, without redeploy if dynamic reseed exists — deferred; meanwhile migration + redeploy is enough.
- (+) Catalog in code + DB allows tests to verify "every endpoint has `require(...)`" and "every cited permission exists".
- (−) Five fixed roles + a granular permission catalog (full matrix in [06 — Security model § Authorization](../06-security-model.md#authorization)) = non-trivial matrix; mitigated with a scripted seed and a test asserting `len(role_permissions) == sum(len(defaults[r]) for r in roles)`.
- (−) Ownership in the query layer means every repository with an owner must respect the rule; mitigable with an `OwnedAggregateRepository` mixin.
- (−) Frontend needs to know the actor's `permissions_set` to show/hide actions (buttons). Exposed via `GET /v1/me` (extending the sprint 03 response).
- (−) 60-second per-process cache means after a mapping reseed there is up to 60 s of propagation. Acceptable; the alternative (cache invalidation by event) falls outside the MVP.

## Alternatives
- **Flat RBAC (hierarchical role)** — rejected: 5 ordered levels cannot express "the salesperson can issue an invoice but not void it" without escalating the whole role.
- **ABAC (OPA/Casbin-style policies)** — rejected: policy engine + DSL is over-engineering for rules that reduce to "role has permission" + "is owner of the resource".
- **Granular RBAC with permission catalog + hybrid ownership** — chosen. Permissions in `<resource>:<action>[-all]` form. Each role maps to a fixed set of permissions (seeded in a migration). Hybrid ownership: pairs `*:read` (own) and `*:read-all` (all in the tenant) where applicable.
- **Per-tenant custom roles** — rejected for MVP. Reopenable if a production tenant demands it.

## Revisit triggers
- A production tenant requires custom roles or per-instance permissions.
- The role-permission matrix grows past ~150 permissions — flat catalog becomes unmanageable.
- 60-second cache propagation becomes unacceptable due to a permission revocation requirement.
- An audit identifies an enumeration leak from the 403/404 split.

## Addendum (2026-05-30) — Per-user permission overrides
Sprint 3.14 spec'd `PATCH /v1/tenants/{id}/members/{user_id}/permissions` and a `tenant_member_permissions` table to grant or revoke individual permissions per member without changing their role, but never implemented the endpoint or the UI. The spec lived under `openspec/changes/restructure-sidebar-empresa-and-account/specs/tenants-http/spec.md`.

**Decision**: drop the override surface from the MVP. The `Empresa → Usuarios` page exposes role changes only. SMBs in Nicaragua choose between five roles; the operator feedback that drove sprint 3.14 was about *where* to manage members, not about granular per-permission grants. The existing "Out of MVP" bullet "Per-instance permissions" already covers this case; this addendum makes the deferral explicit so the spec file can be deleted without losing the rationale.

**If reopened**: the spec text remains in the archived change (`openspec/changes/restructure-sidebar-empresa-and-account/`) and matches the canonical RBAC shape (catalog code + RLS-protected table + 60s-cache invalidation via row `created_at`). Re-promote it when a production tenant requests granular grants.
