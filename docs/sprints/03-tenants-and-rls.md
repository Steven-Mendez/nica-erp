# Sprint 03 — `tenants` context + multi-tenancy with RLS + granular RBAC + deploy

**Goal.** Two tenants created, isolated by Postgres RLS, e2e isolation test green locally and on AWS. Initial permission catalog + `require_permission` dependency operational. Sprint swap: GUC `app.tenant_id` against real RDS under real Cognito. Two canonical patterns reused by sprints 04-08 land here: **per-table RLS for tenant-scoped tables** and **per-endpoint permission enforcement**.

---

## Dependencies

- [00](00-walking-skeleton.md) (`UnitOfWork`, `TenantContext`, RLS scaffolding); [01](01-aws-wiring-rolling-deploys.md) (Cognito User Pool); [02](02-identity-and-rbac.md) (`identity` with real users, `EmailSender` for invitations).
- **Custom attribute `custom:active_tenant`** already exists on the User Pool from [sprint 01](01-aws-wiring-rolling-deploys.md); this sprint is the first to populate it via `SwitchActiveTenant`. Schema in [`../06-security-model.md`](../06-security-model.md).

---

## `tenants/` context

- Aggregates: `Tenant`, `Membership`, `Invitation`.
- VOs: `Ruc` (validation), `Municipality` (extensible enum), `Regime` (general/simplified), `AuthorizationDgi` (number + validity).
- Events: `TenantCreated`, `MemberInvited`, `MemberJoined`, `MemberRemoved`, `InvitationCancelled`, `MemberRoleChanged`.
- `Tenant` carries NI fiscal metadata: `ruc`, `regime`, `municipality`, `authorization_dgi`, `fiscal_address`, `is_withholder`.
- `Membership(user_id, tenant_id, role)` — roles: `owner`, `admin`, `accountant`, `salesperson`, `viewer`. Defined as enum in `tenants/domain/role.py`; constraint `UNIQUE (tenant_id) WHERE role='owner'` guarantees a single owner per tenant ([ADR-0022](../adr/0022-rbac-model.md)).
- `Invitation` with signed token, 7-day expiration, proposed `role`.

---

## Canonical RLS pattern (defined here, reused in 04-08)

Every tenant-scoped table:

```sql
ALTER TABLE <table> ADD COLUMN tenant_id UUID NOT NULL;
CREATE INDEX idx_<table>_tenant ON <table>(tenant_id);
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <table>
  USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

`USING` filters reads/updates; `WITH CHECK` blocks inserts/updates with a `tenant_id` different from the GUC. **Both clauses with the same expression, always.** The `true` in `current_setting(..., true)` returns `NULL` when the GUC is not set (instead of erroring) → allows bootstrap before the middleware's `SET LOCAL`. Rationale in [ADR-0002](../adr/0002-postgres-rls.md).

**Migration 0003** applies the pattern to the sprint's new tenant-scoped tables (`invitations`) and to `tenant_members` with its special policy (below). **`outbox`, `processed_events` and `idempotency_keys` remain WITHOUT RLS by design** — the outbox publisher is a system process that sees all tenants ([`../05-multi-tenancy.md` §Global tables without RLS](../05-multi-tenancy.md#global-tables-without-rls), [`../07-events-and-outbox.md`](../07-events-and-outbox.md), [ADR-0002](../adr/0002-postgres-rls.md)). Access is restricted by DB role, not by policy. Future tenant-scoped tables are covered in their sprints.

### `tenant_members` table (bridge)

```sql
CREATE TABLE tenant_members (
  id          UUID PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'active',
  joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  removed_at  TIMESTAMPTZ,
  UNIQUE (user_id, tenant_id)
);
ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_members FORCE ROW LEVEL SECURITY;
```

Special policy — the user must be able to read their memberships without an active tenant:

```sql
CREATE POLICY tenant_members_self ON tenant_members
  USING      (user_id   = current_setting('app.current_user_id', true)::uuid
              OR tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

---

## Granular RBAC — catalog and enforcement

[ADR-0022](../adr/0022-rbac-model.md). Here we create the tables, the initial seed (only the `tenants` context; later sprints extend with `INSERT ... ON CONFLICT DO NOTHING`), and the `require_permission` dependency each router consumes.

### Tables (global, no RLS)

```sql
CREATE TABLE permissions (
  code         TEXT PRIMARY KEY,
  resource     TEXT NOT NULL,
  action       TEXT NOT NULL,
  scope        TEXT NOT NULL CHECK (scope IN ('own','all','na')),
  description  TEXT NOT NULL
);

CREATE TABLE role_permissions (
  role        TEXT NOT NULL,
  permission  TEXT NOT NULL REFERENCES permissions(code) ON DELETE RESTRICT,
  PRIMARY KEY (role, permission)
);
```

### Python catalog (source of truth)

`shared_kernel/permissions/catalog.py` declares the constants. Migration 0003 runs the seed by reading this module.

```python
# shared_kernel/permissions/catalog.py
@dataclass(frozen=True)
class Permission:
    code: str
    resource: str
    action: str
    scope: Literal["own", "all", "na"]
    description: str

TENANT_PERMISSIONS: tuple[Permission, ...] = (
    Permission("tenant:read",          "tenant",  "read",        "na", "View tenant fiscal metadata"),
    Permission("tenant:write",         "tenant",  "write",       "na", "Edit fiscal metadata"),
    Permission("members:read",         "members", "read",        "na", "List tenant members"),
    Permission("members:invite",       "members", "invite",      "na", "Invite new members"),
    Permission("members:update-role",  "members", "update-role", "na", "Change a member's role"),
    Permission("members:remove",       "members", "remove",      "na", "Remove members from the tenant"),
)

ROLES: tuple[str, ...] = ("viewer", "salesperson", "accountant", "admin", "owner")

DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer":      frozenset({"tenant:read"}),
    "salesperson": frozenset({"tenant:read"}),
    "accountant":  frozenset({"tenant:read", "members:read"}),
    "admin":       frozenset({"tenant:read", "tenant:write", "members:read",
                              "members:invite", "members:update-role", "members:remove"}),
    "owner":       frozenset({"tenant:read", "tenant:write", "members:read",
                              "members:invite", "members:update-role", "members:remove"}),
}
```

Sprints 04-08 extend `TENANT_PERMISSIONS` with `CATALOG_PERMISSIONS`, `SALES_PERMISSIONS`, etc., and add to `DEFAULT_ROLE_PERMISSIONS[role]`.

### `require` dependency

`bootstrap/dependencies.py`:

```python
async def current_actor(request: Request, session: AsyncSession = Depends(get_session)) -> Actor:
    user_id = ContextVar_user_id.get()
    tenant_id = ContextVar_tenant_id.get()
    role = await get_membership_role(session, user_id, tenant_id)
    perms = await _permissions_for(role, session)
    return Actor(user_id=user_id, tenant_id=tenant_id, role=role, permissions=perms)

# Cache TTL 60 s per process over (role -> frozenset[str]).
# lru_cache does not support TTL; use dict + expiry or cachetools.TTLCache.
_PERMS_CACHE: dict[str, tuple[float, frozenset[str]]] = {}
_PERMS_TTL_SECONDS = 60.0

async def _permissions_for(role: str, session: AsyncSession) -> frozenset[str]:
    now = time.monotonic()
    hit = _PERMS_CACHE.get(role)
    if hit and now - hit[0] < _PERMS_TTL_SECONDS:
        return hit[1]
    rows = await session.execute(
        select(RolePermissionRow.permission).where(RolePermissionRow.role == role)
    )
    perms = frozenset(rows.scalars())
    _PERMS_CACHE[role] = (now, perms)
    return perms

def require(*codes: str):
    async def _check(actor: Actor = Depends(current_actor)) -> Actor:
        missing = [c for c in codes if c not in actor.permissions]
        if missing:
            raise ForbiddenError(missing=missing)
        return actor
    return _check
```

Changes in `role_permissions` propagate within ≤ 60 s without explicit invalidation.

`ForbiddenError` maps to 403 RFC 7807 `type=missing-permission` ([ADR-0015](../adr/0015-rfc7807-errors.md)).

### Sprint endpoints with wired permissions

```python
@router.patch("/v1/tenants/{id}",
              dependencies=[Depends(require("tenant:write"))])
async def update_tenant(...): ...

@router.get("/v1/tenants/{id}/members",
            dependencies=[Depends(require("members:read"))])
async def list_members(...): ...

@router.post("/v1/tenants/{id}/invitations",
             dependencies=[Depends(require("members:invite"))])
async def invite(...): ...
```

### `GET /v1/me` exposes the set

`/v1/me` now returns `permissions: string[]` and `role: string` in addition to the fields from [sprint 02](02-identity-and-rbac.md). The SPA uses this to condition UI; the backend remains the source of truth.

### Sprint gate tests (block merge)

1. **RLS isolation** (see §Critical test below).
2. **Permission matrix**: `pytest -k test_role_permission_matrix` enumerates the `role_permissions` table and compares with `DEFAULT_ROLE_PERMISSIONS`. Difference → fail.
3. **Endpoint coverage**: `pytest -k test_all_endpoints_require_permission` parses the registered FastAPI routes and requires that every non-public route has at least one `Depends(require(...))` or is allow-listed (`/v1/auth/*`, `/v1/me`, `/v1/tenants` POST, `/v1/invitations/{token}/accept`).
4. **403 vs 404**: three tests verify that a `viewer` receives 403 when attempting `tenant:write` and 404 when requesting `/v1/tenants/{another_id}` (foreign tenant).

---

## Middleware with `SET LOCAL`

`tenant_middleware.py` (after the auth middleware):

1. Reads `custom:active_tenant` from the JWT.
2. If empty → allows only the without-tenant whitelist from [sprint 02](02-identity-and-rbac.md) (includes `POST /v1/tenants`; after creating the first tenant the user calls `POST /v1/tenants/{id}/switch` to obtain a JWT with the claim).
3. Validates active membership (`tenant_members`).
4. `current_tenant.set(uuid)` in ContextVar.
5. On opening a transaction: `SET LOCAL app.tenant_id = '<uuid>'` and `SET LOCAL app.current_user_id = '<uuid>'`.

---

## Use cases

`CreateTenant`, `GetMyTenants`, `GetTenant`, `UpdateTenant`, `InviteMember`, `AcceptInvitation`, `CancelInvitation`, `RemoveMember`, `SwitchActiveTenant` (updates `custom:active_tenant` via `IdentityProvider.update_active_tenant()`).

Endpoints: [`../08-api-conventions.md` #tenants](../08-api-conventions.md#tenants).

---

## Critical isolation test (sprint gate)

E2E that **blocks merge** if it does not pass:

```python
@pytest.mark.e2e
async def test_tenant_isolation_via_rls():
    user_a = await register_and_login("a@test.dev")
    user_b = await register_and_login("b@test.dev")
    tenant_a = await create_tenant(user_a, name="Empresa A", ruc="...")
    tenant_b = await create_tenant(user_b, name="Empresa B", ruc="...")
    await invite_member(user_a, tenant_a, email="x@test.dev")

    # B with tenant B does not see A's data
    r = await get(user_b, f"/v1/tenants/{tenant_a.id}/invitations")
    assert r.status_code == 404

    # Manipulation: B forges JWT with active_tenant=A
    forged = forge_jwt(user_b.id, email=user_b.email, active_tenant=tenant_a.id, jwt_secret=...)
    r = await get_with_token(forged, f"/v1/tenants/{tenant_a.id}/members")
    assert r.status_code == 403   # middleware detects B is not a member
```

`forge_jwt` lives in `contexts/identity/testing.py` (not importable from productive adapters per `import-linter`); reuses the HS256 encoder of `IdentityProviderLocal` for identical shape. AWS variant (test User Pool + `AdminInitiateAuth`) runs in contract tests of [sprint 09](09-mvp-validation.md).

---

## Frontend

Routes `/tenants/new`, `/tenants`, `/tenants/$tenantId/members`, `/invitations/$token/accept`. `TenantSwitcher` in the Topbar invokes `POST /v1/tenants/{id}/switch`, receives a fresh JWT with `custom:active_tenant`, persists in the auth store, fires `queryClient.clear()` + `router.invalidate()`. Rest follows README §Shared patterns.

---

## Verifiable outcome (local)

```bash
TOKEN_A=$(register_and_login "a@test.dev")
curl -X POST localhost:8000/v1/tenants -H "Authorization: Bearer $TOKEN_A" \
  -d '{"name":"Empresa A","ruc":"...","municipality":"Managua","regime":"general"}'
TOKEN_A=$(curl -X POST localhost:8000/v1/tenants/<id>/switch ... | jq -r .access_token)
curl localhost:8000/v1/tenants/<id>/invitations -H "Authorization: Bearer $TOKEN_A"
```

Plus the critical test above green.

---

## Deploy

### Terraform additions

- **Migration 0003**: ALTER `tenants` (placeholder from [sprint 00](00-walking-skeleton.md) migration 0001) to add NI fiscal metadata columns + RLS; CREATE `tenant_members` with its special policy; CREATE `invitations` with standard RLS (canonical pattern above); CREATE `permissions` and `role_permissions` tables (global, no RLS); initial seed from `TENANT_PERMISSIONS` + `DEFAULT_ROLE_PERMISSIONS` ([ADR-0022](../adr/0022-rbac-model.md)). `outbox`, `processed_events` and `idempotency_keys` remain without RLS by design (see [`../05-multi-tenancy.md` §Global tables without RLS](../05-multi-tenancy.md#global-tables-without-rls)).
- **Cognito**: `custom:active_tenant` receives its first real values via `SwitchActiveTenant`. IAM `cognito-idp:AdminUpdateUserAttributes` already comes from [sprint 02](02-identity-and-rbac.md).
- **No new modules**: redeploy of the binary.

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus: two sessions (two browsers/private) create tenants A and B, A invites "x@test.dev" from tenant A, B in tenant B tries to list A's invitations → 404; forge_jwt with `active_tenant=A` for B → 403.

Cost: ~3-5 USD.
