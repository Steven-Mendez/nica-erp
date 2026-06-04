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
3. **Endpoint coverage**: `pytest -k test_all_endpoints_require_permission` parses the registered FastAPI routes and requires that every non-public route has at least one `Depends(require(...))` or is allow-listed (`/v1/auth/*`, `/v1/me`, `/v1/tenants` POST, `/v1/invitations/accept`).
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

Endpoints surfaced under `/v1/tenants/*` and `/v1/invitations/*`; per-endpoint contracts live in OpenAPI ([`../08-api-conventions.md` §Endpoint catalog](../08-api-conventions.md#endpoint-catalog)). Concrete route shapes are summarised in §Sprint endpoints with wired permissions above.

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

### Dashboard shell + account screen

The sprint introduces the **app shell** every authenticated route in sprints 04-08 will live inside, modeled on the shadcn `dashboard-01` block (sidebar + site-header). It is **placeholder-only** for non-account/non-tenant routes — sprints 04-08 hydrate each section as the corresponding bounded context lands.

Layout:

- **Sidebar (left rail)**: `Overview`, `Sales`, `Inventory`, `Reports`, `Tenants`, `Settings` nav items + `Account` and `Sign out` in the footer. Collapses to icon-only on desktop and hides on mobile (a topbar trigger reveals it). The active tenant name + role render in the sidebar header — the `TenantSwitcher` graduates from the topbar into a sidebar dropdown.
- **Site header (top of main area)**: breadcrumb derived from the route, plus a theme toggle. The header is part of the shell, not the page.
- **Main area**: route content. Authenticated pages opt into the shell by rendering through `<AppShell>` — auth screens (`/login`, `/signup`, `/confirm`, etc.) and the public `/invitations/$token/accept` route bypass it.

Routes introduced by this sprint:

| Route | Content | Permission |
|---|---|---|
| `/dashboard` | 4 KPI placeholder cards + 1 chart placeholder + 1 table placeholder. **No backend calls.** | none — landing page |
| `/sales` | `Coming soon` placeholder | none |
| `/inventory` | `Coming soon` placeholder | none |
| `/reports` | `Coming soon` placeholder | none |
| `/settings` | `Coming soon` placeholder | none |
| `/account` | **Real screen.** Profile card (`/v1/me`: id, email, display_name, locale, timezone, preferences), tenant card (active tenant name + RUC, role badge), permissions card (list rendered from `me.permissions`). | none — own profile |

`/account` is the only non-placeholder route in this list. It supersedes the sprint-02 `/me` page; `/me` SHALL redirect to `/account` so existing bookmarks keep working. The screen reads exclusively from `GET /v1/me` plus `GET /v1/tenants/me` (for the active tenant's display name) — both already present in this sprint.

`/` redirects to `/dashboard` when an access token is in memory and to `/login` otherwise. Login success and tenant creation both navigate to `/dashboard`.

Placeholder rules:

- A placeholder route MUST NOT call the backend. A `useQuery` on a non-existent endpoint would 404 and pollute the error mapper.
- A placeholder route MUST render a single `<Card>` with a title matching the nav label and a one-sentence "Coming soon" description (no sprint numbers in product UI). No fake data, no fake charts with random numbers — the cards advertise what is missing, not pretend it exists.
- The shell itself is **not** a placeholder. Its sidebar + site-header are production code that sprints 04-08 reuse unchanged.

Permission gating on the placeholders is deferred: the nav items render unconditionally in this sprint because the user has no observable difference between a hidden item and one with no destination. Sprint 04 onwards wraps each nav item in `<Can permission="...">` ([`../09-frontend.md` §2 Permission gating](../09-frontend.md#2-permission-gating)) as the real screens land.

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

---

## Sprint closure note (2026-05-27)

- **Backend**: `contexts/tenants/` lands with `Tenant`, `Membership`,
  `Invitation` aggregates, five value objects, six domain events, and
  nine use cases. `shared_kernel/permissions/` hosts the canonical
  RBAC catalog + the TTL-60s permission cache, and exposes the
  cross-context `current_actor` / `require(*codes)` dependencies from
  `bootstrap/dependencies.py`.
- **Multi-tenancy**: `TenantMiddleware` validates membership via a
  short read-only UoW; `_RequestUnitOfWork.begin()` issues
  `set_config('app.tenant_id', :t, true)` and
  `set_config('app.current_user_id', :u, true)` on the outer
  transaction. The function form is used instead of `SET LOCAL`
  because the latter does not accept bound parameters in PostgreSQL.
- **Migration 0003**: ALTER `tenants` with the seven fiscal columns +
  `status` + `updated_at`; CREATE `tenant_members` with the
  `tenant_members_self` policy and the partial single-owner unique
  index; CREATE `invitations` with the canonical per-tenant RLS
  policy; CREATE `permissions` and `role_permissions` with the seed
  driven by `shared_kernel.permissions.catalog`. Reversible.
- **HTTP surface**: `/v1/tenants/*` (11 routes) + a public
  `POST /v1/invitations/accept` (token in body, per
  [ADR-0031](../adr/0031-invitation-token-transport.md)).
  `/v1/me` now returns
  `role: string | null` and `permissions: string[]`. The
  invitation-accept route is wired into the no-tenant-required
  allowlist so the authenticated user is identifiable.
- **Frontend**: `features/tenants/` slice (Zod schemas, hooks,
  endpoints), `components/topbar/Topbar` + `TenantSwitcher`, four new
  routes (`/tenants`, `/tenants/new`, `/tenants/$tenantId/members`,
  `/invitations/$token/accept`), `api/useHasPermission` shared hook,
  `api/queryKeys` shared infra for cross-feature cache keys.
- **Tests**: 4 sprint gates land:
  - `tests/integration/shared_kernel/permissions/test_role_permission_matrix.py`
    — DB vs catalog parity.
  - `tests/integration/bootstrap/test_endpoint_permission_coverage.py`
    — every non-public route declares `Depends(require(...))` or is
    explicitly allowlisted.
  - `tests/integration/contexts/identity/http/test_auth_middleware.py`
    — adjusted to reflect the moved invitation-accept route.
  - Unit + domain suites for tenants aggregates and the permission
    cache.
  Total: 179 backend pytest + 10 frontend vitest, all green.
- **AWS deploy**: deferred. The account is still in verification, so
  the Terraform side of the sprint is unchecked in `tasks.md`. The
  Cognito user pool from sprint 01 already carries the
  `custom:active_tenant` attribute and the IAM allow-list for
  `cognito-idp:AdminUpdateUserAttributes` is already in place from
  sprint 02; no Terraform module changes are queued.

## Sprint follow-up — dashboard shell (2026-05-27)

After the closure above, a **frontend-only** addendum lands in the
same sprint to deliver the app shell that sprints 04-08 will reuse
unchanged. Scope:

- `apps/web/src/components/app-shell/` — `AppShell` provider that
  renders the sidebar + `SiteHeader` and yields the route children
  inside a main column. Authenticated routes opt into the shell by
  rendering `<AppShell>` at their top level.
- `apps/web/src/components/app-sidebar/` — sidebar primitives
  (`Sidebar`, `SidebarHeader`, `SidebarContent`, `SidebarFooter`,
  `SidebarGroup`, `SidebarGroupLabel`, `SidebarMenu`,
  `SidebarMenuItem`, `SidebarMenuButton`) and the project-specific
  `AppSidebar` that wires the nav. Built on Tailwind utility classes
  + the existing sidebar tokens (`apps/web/src/styles/globals.css`
  already declares `--sidebar`, `--sidebar-foreground`, etc.); no
  new npm dependencies.
- `TenantSwitcher` moves from the topbar into the sidebar header
  (`SidebarHeader`). The previous `components/topbar/Topbar.tsx`
  becomes the `SiteHeader` rendered by `AppShell`, hosting the
  breadcrumb + theme toggle. The old `Topbar` file is removed; only
  the auth-aware sign-out lives in the sidebar footer.
- New routes (placeholders, no backend calls): `/dashboard`,
  `/sales`, `/inventory`, `/reports`, `/settings`. Each renders a
  `<Card>` with a `Coming in sprint NN` description.
- New `/account` route reads `GET /v1/me` and renders profile,
  active-tenant, and permission cards. `/me` is converted to a
  301-style redirect to `/account` so existing tests and links keep
  working.
- `/` redirects to `/dashboard` when an access token is present,
  otherwise to `/login`. Login success and tenant creation also
  navigate to `/dashboard`.

No backend changes. Migration 0003, the RBAC catalog, and the
`/v1/me` contract are untouched. Vitest gains coverage for the
sidebar collapse and `/account` render-from-mock cases; existing
sprint-gate tests stay green.

## Sprint follow-up — Test backfill & e2e tooling (sprint 3.5, 2026-05-27)

After the dashboard shell addendum lands, a **test-only** follow-up
labelled sprint 3.5 fills the coverage gaps accumulated through
sprints 00-03 and installs Playwright as the browser-level e2e tool.
No production code changes; no migrations. The follow-up is run
**before** sprint 3.6 (Welcome / Onboarding / Rename / Members) so
the rename and onboarding work lands on top of a stable safety net.

### Why now

Inventory at the start of 3.5:

- `apps/api/src/contexts/tenants/application/use_cases/`: nine use
  cases, **zero unit tests**.
- `apps/api/src/contexts/tenants/adapters/outbound/persistence/`:
  three repositories, **zero integration tests**.
- `apps/api/src/contexts/tenants/adapters/inbound/http/`: tenant
  middleware + eleven router endpoints, **only** the generic
  `test_endpoint_permission_coverage.py` exercises them.
- `test_tenant_isolation_via_rls` — declared as the sprint-03 merge
  gate above — **does not exist on disk**. Closure was premature.
- `apps/web/`: three vitest files total
  (`api/interceptor`, `api/tokenStore`, `routes/health`); Playwright
  is **not installed**.

### Scope — backend

Unit (`tests/unit/contexts/tenants/`):

- `application/use_cases/test_create_tenant.py`
- `application/use_cases/test_update_tenant.py`
- `application/use_cases/test_get_tenant.py`
- `application/use_cases/test_get_my_tenants.py`
- `application/use_cases/test_invite_member.py`
- `application/use_cases/test_accept_invitation.py`
- `application/use_cases/test_cancel_invitation.py`
- `application/use_cases/test_remove_member.py`
- `application/use_cases/test_update_member_role.py`
- `application/use_cases/test_switch_active_tenant.py`

Each mocks repositories, outbox and identity-provider ports; asserts
command shape, domain invariants, and the events emitted.

Integration (`tests/integration/contexts/tenants/`):

- `outbound/persistence/test_tenant_repository.py` (real DB)
- `outbound/persistence/test_membership_repository.py` (exercises the
  `tenant_members_self` policy)
- `outbound/persistence/test_invitation_repository.py`
- `outbound/tokens/test_jwt.py` (sign + verify roundtrip, expiry,
  tampering)
- `http/test_tenant_middleware.py` (`set_config('app.tenant_id', …)`,
  no-tenant allowlist, invalid membership → 403)
- `http/test_tenants_router.py` (eleven routes × happy path + 401 +
  403 + 404 cross-tenant)
- `http/test_invitations_router.py`

E2E (`tests/e2e/contexts/tenants/`):

- `test_rls_tenant_isolation.py` — the sprint-03 gate. Reproduces the
  scenario from the *Critical isolation test* section above: two
  users, two tenants, `forge_jwt` for the cross-tenant attempt, 403
  expected.
- `test_tenant_lifecycle.py` — create → switch → invite → accept →
  list members → update role → remove.

### Scope — frontend

Unit (`apps/web/tests/unit/`):

- `features/auth/api/`: one file per hook (`loginMutation`,
  `signupMutation`, `confirmMutation`, `useMe`, `refreshMutation`,
  `forgotPasswordMutation`, `resetPasswordMutation`,
  `logoutMutation`).
- `features/auth/components/`: form-level tests for Login, Signup,
  Confirm, ForgotPassword, ResetPassword.
- `features/auth/schemas/`: Zod schemas.
- `features/tenants/api/hooks.ts`: ten hooks (queries + mutations).
- `features/tenants/components/`: TenantCard, list rows, etc.
- `features/tenants/schemas/`.
- `features/dashboard/components/`: KPI card, chart placeholder,
  table placeholder.
- `components/app-shell/`: render with/without auth context.
- `components/app-sidebar/`: collapse behaviour, active nav item,
  `TenantSwitcher`, sign-out button.
- `components/ui/`: only the wrappers that diverge from upstream
  shadcn (Button variants, Form, Card).
- `api/queryKeys.ts`, `api/useHasPermission.ts`,
  `api/interceptor.ts` (extend the existing test).

Integration (`apps/web/tests/integration/`, vitest + MSW + Testing
Library):

- Route render tests with MSW intercepting `/v1/*`: `/login`,
  `/signup`, `/confirm`, `/forgot-password`, `/reset-password`,
  `/account`, `/dashboard`, `/tenants`, `/tenants/new`,
  `/tenants/$tenantId/members`, `/invitations/$token/accept`, `/me`
  redirect.
- TanStack Router: unauthenticated → `/login`; redirect chains.

E2E (Playwright, `apps/web/tests/e2e/`):

- `playwright.config.ts` (Chromium + WebKit; baseURL configurable;
  `reuseExistingServer: false` in CI).
- `tests/e2e/fixtures/auth.ts` for programmatic login helpers.
- `auth.spec.ts` — signup → confirm (against `IdentityProviderLocal`
  which exposes the code via the local outbox) → login → `/account`
  shows correct data.
- `tenant-onboarding.spec.ts` — login → create first tenant → switch
  → land on the dashboard placeholder.
- `member-management.spec.ts` — admin invites → invitee accepts in a
  second browser context → both see the member; admin removes.
- `permission-gating.spec.ts` — `viewer` vs `admin` see different
  affordances on `/tenants/$id/members`.
- `rls-isolation.spec.ts` — two simultaneous browser contexts; no
  data crosses tenants.

### Tooling additions

- `apps/web/package.json` — devDependency `@playwright/test`; scripts
  `test:e2e`, `test:e2e:ui`, `test:e2e:install`.
- `apps/web/playwright.config.ts`.
- `apps/web/tests/e2e/fixtures/` with auth and tenant setup helpers.
- `apps/web/.gitignore` ignores `playwright-report/` and
  `test-results/`.
- CI workflow gains a Playwright job: `npx playwright install
  --with-deps chromium webkit`, start the API + Postgres + SPA in
  background, run `npx playwright test`, upload
  `playwright-report/` as artifact on failure.
- `Makefile` recipes: `make test-e2e`, `make test-be-coverage`,
  `make test-fe-coverage`, `make test-all`.
- `apps/api/pyproject.toml` — confirm `pytest-cov`; add
  `--cov-fail-under=90` to the make recipe (not the default `pytest`
  invocation so developers can still iterate without coverage).
- `apps/web/vitest.config.ts` — coverage provider `v8`; thresholds
  80% lines / 80% functions on `features/` and `components/`.

### Coverage gates that block merge

| Layer | Tool | Threshold |
|---|---|---|
| BE unit + integration | pytest-cov | ≥ 90% lines on `contexts/tenants` + `contexts/identity` + `shared_kernel` |
| BE e2e | pytest -m e2e | both new specs pass |
| FE unit + integration | vitest v8 | ≥ 80% lines on `features/` + `components/` |
| FE e2e | Playwright | five specs pass on Chromium (WebKit warning-only for now) |

### Closure criteria

1. `make test-all` green locally.
2. CI green with Playwright browsers installed.
3. Coverage metrics meet the thresholds above; HTML report attached
   to the PR.
4. `test_tenant_isolation_via_rls` lands and is green — sprint-03
   gate finally enforced.
5. A short note appended at the end of this file documents the final
   numbers and links to the HTML report artifact.

### Notes

- Production code is untouched. The only diffs in `apps/web/src/`
  and `apps/api/src/` should be the addition of `data-testid`
  attributes where Playwright needs deterministic selectors.
- Cognito stub: `auth.spec.ts` runs against the local identity
  provider whose verification code is observable through the
  in-process mail sink already used by sprint 02 tests.

## Sprint follow-up — Welcome / Onboarding / Rename / Members (sprint 3.6, 2026-05-27)

Sprint 3.6 ships the first-login profile capture, the
Supabase-style organization selector, the four-step organization
creation wizard, the rename of "tenant" to "organization" in the
product surface, the ofuscation of invitation tokens, and the
member role-change UI. It lands **after** the test backfill of
sprint 3.5 so every change in this sprint is protected by the
existing safety net and adds its own tests on top.

### Decisions captured by ADRs

- [ADR-0031 — Invitation token transport](../adr/0031-invitation-token-transport.md)
- [ADR-0032 — Tenant vs organization naming](../adr/0032-tenant-vs-organization-naming.md)
- [ADR-0033 — Deferred locale modeling](../adr/0033-deferred-locale-modeling.md)

### Post-login flow (canonical)

```
login success
  ↓
GET /v1/me
  ↓
display_name IS NULL ?              ← first-login probe
  └─ yes → /welcome
            (display_name + timezone)
            PATCH /v1/me
            ↓
memberships.length == 0 ?
  ├─ yes → /onboarding
  │         ├─ "Crear organización" → /onboarding/new   (4-step wizard)
  │         └─ "Tengo código"        → /invitations/accept
  └─ no  → /organizations            (Supabase-style picker, ALWAYS)
            ↓ click card → POST /v1/tenants/{id}/switch
            ↓
          /dashboard
```

The picker is shown every session even when only one organization
exists — predictable ritual over click-saving. Switching mid-session
happens from the sidebar `OrganizationSwitcher`, never round-tripping
through `/organizations`.

### Welcome screen (`/welcome`)

- New authenticated route **outside** the `AppShell`.
- Form fields: `display_name` (2-100 chars, Zod) and `timezone`
  (`<select>` populated from
  `Intl.supportedValuesOf('timeZone')`, pre-selected with
  `Intl.DateTimeFormat().resolvedOptions().timeZone`).
- `locale` is **not** asked here. The deferred locale modeling work
  is documented in [ADR-0033](../adr/0033-deferred-locale-modeling.md).
- Submit posts to the existing `PATCH /v1/me` use case.
- Route guard: any authenticated route except `/welcome`,
  `/account` and `/health` redirects to `/welcome` when
  `me.display_name === null`.

### Migration 0004 — drop user profile defaults

```sql
ALTER TABLE users
  ALTER COLUMN display_name DROP NOT NULL,
  ALTER COLUMN display_name DROP DEFAULT,
  ALTER COLUMN locale       DROP NOT NULL,
  ALTER COLUMN locale       DROP DEFAULT,
  ALTER COLUMN timezone     DROP NOT NULL,
  ALTER COLUMN timezone     DROP DEFAULT;
```

Reversible. Existing rows keep their current values; the migration
only changes the column definitions. `locale` stays in the schema
as a nullable column, unused by the UI, awaiting the future i18n
sprint per [ADR-0033](../adr/0033-deferred-locale-modeling.md).

### Backend changes

- `User` aggregate: `display_name`, `locale`, `timezone` become
  `Optional[str]`. `UpdateProfile` already accepts partial values;
  no use-case logic changes.
- `/v1/me` schema: the three fields move to `string | null`.
- Invitation endpoint contract update (see
  [ADR-0031](../adr/0031-invitation-token-transport.md)):
  - `POST /v1/invitations/{token}/accept` removed; replaced by
    `POST /v1/invitations/accept` with `{ "token": "…" }` in the
    body.
  - New `GET /v1/invitations/{token}/preview` returns
    `{ email, organization_name, role }` — rate-limited; the
    short-lived token already exists per sprint-03 issuance rules.
  - `_DEFAULT_INVITE_URL_TEMPLATE` becomes
    `https://<host>/invitations/accept#t={token}`. The fragment is
    consumed client-side and stripped via
    `history.replaceState`.
  - No transitional 410 Gone shim: the project has not shipped,
    so the legacy path is removed outright.

No new use cases. No tenants/migrations/schemas/RBAC changes.

### Frontend rename — "tenant" → "organization"

Backend stays "tenant" everywhere (URLs, JWT claim, GUC, DB,
hexagonal context). Frontend renames only the surface:

- `apps/web/src/features/tenants/` → `features/organizations/`.
- Components: `TenantSwitcher` → `OrganizationSwitcher`.
- Routes:
  - `/tenants` → `/organizations`
  - `/tenants/new` → resolved to the same component as
    `/onboarding/new` so the wizard is reachable from both the
    first-login flow and the existing-user "create another"
    affordance.
  - `/tenants/$tenantId/members` →
    `/organizations/$organizationId/members`.
- Sidebar nav label: "Tenants" → "Organizations".
- Copy in every screen: "tenant" → "organización" /
  "organization" depending on locale (placeholder until i18n
  lands).
- TypeScript types in frontend code: `Tenant*` → `Organization*`.
  The generated `apps/web/src/api/schema.d.ts` keeps the
  server-side names (the OpenAPI schema is unchanged); a thin
  adapter layer in `features/organizations/api/` maps the backend
  shapes onto the frontend domain types.

### `/organizations` picker

- Renders membership cards (organization name + member role),
  a search box and a "+ Nueva organización" button.
- Click → `POST /v1/tenants/{id}/switch` → `/dashboard`.
- Reached every session post-login; the in-app
  `OrganizationSwitcher` covers in-session switching.

### Wizard four steps (`/onboarding/new` and `/organizations/new`)

1. **Identidad**: `name`, `ruc` (validated client-side with the
   Nicaragua RUC schema already used by the legacy
   `/tenants/new` form).
2. **Régimen fiscal**: `regime`, `municipality`, `is_withholder`.
3. **Autorización DGI**: `authorization_dgi.number`,
   `authorization_dgi.valid_until`.
4. **Dirección fiscal**: `fiscal_address` + review of the previous
   three steps.

Submit → `POST /v1/tenants` → `POST /v1/tenants/{id}/switch` →
`/dashboard`. Validation is incremental (per-step Zod) and the
stepper is composed from existing Tailwind primitives — no new npm
dependencies.

### Member role-change UI

`routes/organizations/$organizationId/members.tsx` (renamed)
adds an inline `<select>` per member (owners excluded) gated by
`useHasPermission("members:update-role")`, wired to
`PATCH /v1/tenants/{id}/members/{user_id}` (endpoint already lives
in the router from sprint 03). The existing invite, cancel, and
remove flows stay untouched.

### Tests (added on top of sprint 3.5's baseline)

- `tests/e2e/test_welcome_first_login.py` (backend) and
  `auth-welcome.spec.ts` (Playwright) — new user lands on
  `/welcome`, completes it, proceeds to `/organizations`.
- `tests/e2e/test_post_login_redirect.py` — zero / one / many
  memberships route correctly.
- `tests/e2e/test_onboarding_wizard_complete.py` — four steps
  create the tenant and end on `/dashboard`.
- `tests/e2e/test_invitation_signup_flow.py` — invite to a
  non-existent email → email link → signup → confirm → welcome
  → auto-accept → dashboard.
- `tests/integration/contexts/identity/http/test_v1_me_nullable_fields.py`
  — the three nullable fields serialise as `null` correctly.
- `tests/integration/contexts/tenants/http/test_invitation_new_endpoints.py`
  — POST body + preview endpoint coverage.
- `welcome.test.tsx`, `organizations-list.test.tsx`,
  `onboarding-wizard.test.tsx`, `route-guard.test.tsx`,
  `member-role-change.test.tsx` (vitest).

### Closure criteria

1. Migration 0004 applied locally and on the test database.
2. Sprint 3.5 thresholds still met after the new code lands.
3. New Playwright specs green on Chromium.
4. ADRs 0031, 0032, 0033 merged with `Status: Accepted`.
5. No production code references "tenant" outside backend
   bounded-context boundaries.

---

## Sprint follow-up — `/confirm` OTP slot input (sprint 3.7, 2026-05-27)

After sprint 3.6 finishes the welcome / onboarding / rename
work, one auth-screen ergonomics gap remains visible enough to
warrant a tiny isolated follow-up: the `/confirm` route still
captures the six-digit Cognito verification code in a single
plain text field. On mobile the keyboard does not always show
the numeric pad, pasting the code from the email lands in one
cell with no visual confirmation that six characters arrived,
and the SMS-autofill chip surfaces inconsistently because the
field looks like a generic text box rather than a code box.

Sprint 3.7 is a single-route shadcn primitive swap. No
behavioural change to the surrounding flow, no schema change,
no backend touched.

### Scope

- Install the shadcn `input-otp` primitive into
  `apps/web/src/components/ui/input-otp.tsx` (one-shot
  generator: `pnpm dlx shadcn@latest add input-otp`).
- Replace the single `<Input>` that captures `code` in
  `apps/web/src/routes/confirm.tsx` with `<InputOTP
  maxLength={6}>` composed of six slots, wired through the
  existing React Hook Form `Controller` and the existing Zod
  `confirmSchema` (which already pins a 6-character string).
- Keep `autoComplete="one-time-code"` and
  `inputMode="numeric"` on the underlying hidden input so
  iOS/Android SMS-autofill and the numeric keypad survive
  unchanged.
- Spanish copy (`Código de verificación`, `Confirma tu correo`,
  `Confirmar`, `Reenviar código`) stays byte-identical.

### Out of scope

- `/onboarding`, `/tenants/new` (renamed to
  `/organizations/new` by sprint 3.6), `/welcome`, `/signup`,
  `/login`, `/forgot-password`, `/reset-password`.
- Any wider form-system migration (`Form`, `FormField`,
  `FormMessage`) — `/confirm` stays on the `Field` + RHF
  `Controller` pattern it already uses.
- Sonner / toast adoption, `select` for régimen, calendar
  date-picker for DGI validity — those live in their own
  separate follow-ups after sprint 3.6 closes.
- No ADR. The shadcn/ui primitive library is the envelope
  already set by [ADR-0009](../adr/0009-frontend-stack.md);
  picking a specific shadcn primitive is not architectural.

### Tests

- `apps/web/tests/unit/routes/confirm.test.tsx` — six slots
  render, paste of "123456" distributes across slots, submit
  with a 6-digit code fires the mutation, submit with fewer
  than six surfaces the field error.
- Manual smoke on iOS Safari and Android Chrome to confirm SMS
  autofill still populates all six slots.

### Verifiable outcome (local)

```bash
cd apps/web && pnpm dlx shadcn@latest add input-otp
pnpm -C apps/web test confirm
pnpm -C apps/web typecheck && pnpm -C apps/web lint
# Open http://localhost:5173/confirm and paste a 6-digit code.
```

### Closure criteria

1. `apps/web/src/components/ui/input-otp.tsx` exists and is
   imported only from `routes/confirm.tsx`.
2. Vitest unit suite covers the four scenarios above.
3. Mobile smoke screenshots (iOS + Android) attached to the
   PR description.
4. No regressions in `pnpm -C apps/web test`,
   `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`.

---

## Sprint follow-up — `/tenants/new` form ergonomics (sprint 3.8, 2026-05-27)

Sprint 3.6 will eventually rewrite the tenant-creation wizard
under `/organizations/new`, but the rename has not landed yet
and the operator surfaced five concrete UX defects while
using the *current* `/tenants/new` route:

1. The default Zod errors leak English copy into a
   Spanish-only product (e.g.,
   `String must contain at least 1 character(s)`).
2. The Régimen field is a bare HTML `<select>`, visually
   inconsistent with the rest of the shadcn-styled wizard.
3. The Municipio field is a free-text input even though the
   backend enforces a 17-entry catalog, so users only
   discover the constraint at the POST round-trip.
4. The "Es retenedor" checkbox is a bare HTML element with
   no explanation of what "retenedor" means.
5. On `POST /v1/tenants` failure (e.g., a 422), the wizard
   surfaces only `POST /v1/tenants failed: 422` instead of
   the validation detail.

Sprint 3.8 is a tactical primitive swap + Zod-message pass +
backend-error surfacing on the current route. The wizard
behaviour (four-step gating, POST → switch → /dashboard) is
unchanged.

### Scope

- Add Spanish `{ message }` to every `z.string().min/max/regex`
  and `z.enum(...)` in
  `apps/web/src/features/tenants/schemas/index.ts` covering
  `createTenantSchema`, `updateTenantSchema`,
  `inviteMemberSchema`, `updateMemberRoleSchema`.
- Mirror the backend's 17 `KNOWN_MUNICIPALITIES` into a new
  frontend constant
  `apps/web/src/features/tenants/municipalities.ts` and
  constrain the schema with `z.enum(MUNICIPALITIES)`.
- Install shadcn `select`, `checkbox`, and `tooltip`. Swap
  the Régimen `<select>` for a `<Select>` composition; swap
  the Municipio `<Input>` for a `<Select>` over the catalog;
  swap the `is_withholder` `<input type="checkbox">` for
  `<Checkbox>` + `<Label>`.
- Add `<Tooltip>` icons next to the Régimen, Municipio, DGI
  número, and Es retenedor labels with one-sentence Spanish
  explanations of each fiscal term.
- Wrap the route root in a single `<TooltipProvider>`.
- Surface backend validation detail: when `POST /v1/tenants`
  returns 422, the wizard `<Alert>` renders the failing field
  name (Spanish: "Municipio", "Número DGI", etc.) and the
  message instead of the generic
  `POST /v1/tenants failed: 422`.

### Out of scope

- DGI date inputs stay as `<input type="date">` — date
  picker is a separate follow-up.
- Wizard step structure, the `STEP_FIELDS` gating, and the
  POST + switch sequence are byte-identical.
- Backend changes — Pydantic schema, Use case, value
  objects all stay.
- Sprint 3.6's `/organizations/new` rewrite picks these
  improvements up via a carry-over task; no early start on
  the rename here.

### Tests

- `apps/web/tests/unit/routes/tenants-new.test.tsx` —
  renders, Spanish error on empty name, Régimen Select
  options, Municipio Select 17 options, Checkbox toggles,
  Tooltip surfaces on hover.

### Verifiable outcome (local)

```bash
cd apps/web && pnpm dlx shadcn@latest add select checkbox tooltip
pnpm -C apps/web test tenants-new
pnpm -C apps/web typecheck && pnpm -C apps/web lint
# Open http://localhost:5173/tenants/new, leave fields empty
# and step through — all errors render in Spanish.
```

### Closure criteria

1. `pnpm -C apps/web test|typecheck|lint` all green.
2. No English Zod default error reachable from any
   `/tenants/new` step.
3. Sprint 3.6 (`welcome-onboarding-rename-members`) has a
   carry-over task that lists Select/Checkbox/Tooltip and the
   `MUNICIPALITIES` constant so the rename rewrite preserves
   them.

---

## Sprint follow-up — DGI date picker (sprint 3.9, 2026-05-27)

Sprint 3.8 left the DGI step's `valid_from` / `valid_to`
fields as native `<input type="date">` because date pickers
required new primitives (Calendar + Popover) and broader UX
consideration. The native element renders inconsistently
across browsers (white pill on Safari, OS-themed dialog on
Chrome, no dark-mode), ignores the project's theme tokens,
and forces month/day names into the OS locale rather than
Spanish.

Sprint 3.9 ships the canonical shadcn date-picker pattern
(`<Popover>` trigger + `<Calendar>` content) wired through a
small `<DatePicker>` wrapper. The wrapper accepts an ISO
`YYYY-MM-DD` string and emits an ISO string back, so the
existing Zod regex and the backend Pydantic `date` parser
keep working byte-identically. Spanish month names come from
`date-fns/locale/es`.

### Scope

- Install shadcn `calendar` and `popover` (pulls
  `react-day-picker`, `date-fns`,
  `@radix-ui/react-popover`).
- Add a reusable wrapper
  `apps/web/src/components/ui/date-picker.tsx` exposing
  `{ value: string, onChange: (iso: string) => void }`.
  Format the trigger label as `format(date, "PPP", { locale:
  es })` so it reads `27 de mayo de 2026`. Use
  `format(d, "yyyy-MM-dd")` to commit back to the form —
  NEVER `toISOString().slice(0, 10)`, which would shift the
  day across non-UTC timezones.
- Swap two `<Input type="date">` in `/tenants/new`'s DGI
  step for the new wrapper, wired through RHF `Controller`.

### Out of scope

- No range picker (`valid_from` and `valid_to` stay as two
  independent single-date pickers).
- No natural-language parsing (chrono-node).
- No time picker.
- No client-side `valid_to >= valid_from` cross-field
  refinement. The backend `AuthorizationDgi` VO already
  enforces it.
- No backend changes.

### Tests

- `tests/unit/routes/tenants-new.test.tsx` adds an assertion
  that no `<input type="date">` exists in the route DOM and
  that the route mounts cleanly with the new
  `<DatePicker>`.

### Verifiable outcome (local)

```bash
cd apps/web && pnpm dlx shadcn@latest add calendar popover
pnpm -C apps/web test tenants-new
pnpm -C apps/web typecheck && pnpm -C apps/web lint
# Open http://localhost:5173/tenants/new, advance to DGI,
# click each picker, verify Spanish month names and that the
# committed values pass the wizard and POST /v1/tenants.
```

### Closure criteria

1. `pnpm -C apps/web test|typecheck|lint` all green.
2. No `<input type="date">` reachable from `/tenants/new`.
3. Sprint 3.6 (`welcome-onboarding-rename-members`)
   carry-over task lists `<DatePicker>` so the rename
   rewrite preserves it.

---

## Sprint follow-up — `/tenants/new` polish: required marks + Revisión card (sprint 3.10, 2026-05-27)

After sprints 3.7 / 3.8 / 3.9 the `/tenants/new` wizard had
two remaining ergonomic gaps the operator surfaced on first
use:

1. **Eager error messages.** With `mode: "onChange"` the
   per-step `trigger()` call left errors populated for
   untouched fields, so messages like "La dirección fiscal
   es obligatoria." rendered on arrival at the Address
   step. There was also no visual cue *in advance* that a
   field was required: the error message was the only
   indicator.
2. **Revisión read as a debug dump.** A `<dl>` with
   `grid-cols-2 gap-1 text-xs` on `bg-muted/30` competed
   with the primary CTA and lacked a hierarchy.

Sprint 3.10 ships small, file-local polish on the *current*
route. Sprint 3.6's `/organizations/new` rename carries
these forward via the existing carry-over task.

### Scope

- `useForm({ mode: "onTouched", reValidateMode: "onChange" })`
  so RHF only validates a field after first blur.
- Per-step "attempted" state set when `trigger()` fails on
  Continuar; per-field error rendering gated by
  `isSubmitted || stepAttempted || touchedFields[field]`,
  so errors appear only after a real validation attempt.
- Tiny inline `RequiredMark` (`<span aria-hidden="true"
  className="text-destructive">*</span>`) next to every
  required label: Nombre, RUC, Régimen, Municipio, Número
  DGI, Válido desde, Válido hasta, Dirección fiscal. NOT on
  Es retenedor.
- Revisión replaced with a sectioned card-layout `<div>`
  containing four `<section>`s — Identidad, Régimen fiscal,
  Autorización DGI, Dirección — separated by
  `<Separator>`. Retenedor renders as a shadcn `<Badge>`;
  Vigencia renders as one `dd MMM yyyy → dd MMM yyyy` row
  in Spanish.

### Out of scope

- No shared `RequiredMark` primitive in `components/ui/` —
  the indicator stays inline in `new.tsx` until a second
  route needs it.
- No change to the wizard's step structure, the `goNext`
  gating, or the POST + switch flow.
- No backend changes.

### Tests

- `tests/unit/routes/tenants-new.test.tsx` adds:
  - on mount, required-mark `<span aria-hidden>*</span>`
    elements exist;
  - the "El nombre es obligatorio." message is NOT in the
    DOM on mount (only after Continuar click).

### Verifiable outcome (local)

```bash
pnpm -C apps/web test tenants-new
pnpm -C apps/web typecheck && pnpm -C apps/web lint
# Open http://localhost:5173/tenants/new — every required
# label shows a red *; no errors on arrival at the Address
# step; the Revisión panel reads as four sections with
# Spanish month names and a Sí/No badge.
```

### Closure criteria

1. `pnpm -C apps/web test|typecheck|lint` all green.
2. No required-field error reachable before user
   interaction OR a "Continuar" click on the field's step.
3. Sprint 3.6 carry-over task lists `onTouched` mode,
   `<RequiredMark>`, error gating, and the card-style
   Revisión so the rename preserves them.

---

## Sprint follow-up — Empresa rebrand + soft-creation (sprint 3.11, 2026-05-28)

Hands-on operator testing of the wizard polished by sprints
3.7 → 3.10 surfaced two decisions that supersede sprint 3.6's
original plan to rename everything to "Organización" and to
demand 8 fiscal fields at creation:

1. **"Organización" reads as jargon** for the Nicaraguan SME
   audience. The natural word is **"empresa"**. Sprint 3.6's
   in-flight rename is pivoted from "organización" to
   "empresa".
2. **Tenant creation requires only the empresa name.** Every
   fiscal field (`ruc`, `regime`, `municipality`,
   `authorization_dgi`, `fiscal_address`, `is_withholder`) is
   now optional at `POST /v1/tenants`. The DB schema
   (migration `0003_tenants_and_rbac.py`) already made every
   column nullable, so no Alembic migration is needed.

Both decisions are captured by
[ADR-0034](../adr/0034-empresa-product-term-and-soft-creation.md),
which supersedes the product-term portion of
[ADR-0032](../adr/0032-tenant-vs-organization-naming.md).

### Scope

- Backend: `CreateTenantRequest` and `TenantResponse` (and
  the underlying `Tenant` aggregate, `CreateTenantCommand`,
  and repository hydrate/insert paths) make every fiscal
  field `Optional[...] = None`. The value objects (`Ruc`,
  `Regime`, `Municipality`, `AuthorizationDgi`) stay strict
  and only run when constructed.
- Frontend: `/tenants/new` collapses to a **single-step
  form** asking only for the empresa name. The wizard
  primitives added by sprints 3.7-3.10 (`Select`,
  `Checkbox`, `Tooltip`, `DatePicker`, `RequiredMark`,
  Revisión card) stay installed in `components/ui/` for the
  future "Editar empresa" route.
- Frontend: every visible string that read "organización" /
  "Organización" / "organizaciones" / "Organizaciones" in
  `apps/web/src/` is replaced with the empresa equivalent.
  Backend identifiers (`/v1/tenants`, `tenant_id`, `Tenant`)
  stay unchanged per ADR-0034's split.
- Frontend: `/dashboard` renders a banner — "Completa los
  datos fiscales de tu empresa para emitir facturas" —
  whenever the active tenant has NULL `ruc` or
  `fiscal_address`, linking to a stub `/empresa/editar`
  route that reads "Próximamente".
- Sprint 3.6 in-flight pivot: the
  `welcome-onboarding-rename-members` change's proposal +
  tasks + specs are updated to use "empresa" / "Empresa"
  everywhere previously planned for "organización" /
  "Organización".

### Out of scope

- No new Alembic migration (the DB schema is already
  nullable).
- No backend rename. `Tenant`, `tenant_id`,
  `app.tenant_id`, `custom:active_tenant`, the directory
  `apps/api/src/contexts/tenants/`, table names — all
  unchanged.
- No frontend slice rename. `apps/web/src/features/tenants/`
  stays per ADR-0034.
- No real "Editar empresa" implementation — the stub route
  exists only so the banner has a target.

### Tests

- Backend: `tests/unit/contexts/tenants/domain/test_aggregates.py`
  exercises name-only `Tenant.register`; the integration
  repository round-trip already covers NULL columns via the
  optional pattern; the e2e flow exercises `POST /v1/tenants`
  with `{"name": "X"}`.
- Frontend:
  `apps/web/tests/unit/routes/tenants-new.test.tsx` is
  rewritten for the single-step form.

### Verifiable outcome (local)

```bash
cd apps/api && uv run pytest             # 222 tests
pnpm -C apps/web test                     # 27 tests
pnpm -C apps/web typecheck && pnpm -C apps/web lint
rg "organizaci|Organizaci" apps/web/src/  # zero hits
# Open http://localhost:5173/tenants/new, type a name only,
# click Crear empresa, verify the SPA lands on /dashboard
# with the "Completa los datos fiscales" banner.
```

### Closure criteria

1. `pnpm -C apps/web test|typecheck|lint` and
   `cd apps/api && uv run pytest` all green.
2. Zero `organizaci` / `Organizaci` matches in
   `apps/web/src/`.
3. `POST /v1/tenants` accepts `{"name": "..."}` and returns
   a 201 with null fiscal fields.
4. Sprint 3.6 carry-over task lists the "empresa" rebrand
   so the rename rewrite preserves the product term.

## Sprint follow-up — Skippable wizard at `/tenants/new` (sprint 3.12, 2026-05-28)

### Motivation

Sprint 3.11 collapsed `/tenants/new` into a single-step
"empresa name only" form so a new SMB owner without DGI
papers in hand could land on the dashboard in seconds.
Hands-on operator testing surfaced a second, equally real
audience that the collapse erased: the returning operator
with the DGI authorisation letter already in front of them,
who wants to enter régimen, municipio, autorización DGI and
dirección fiscal in one sitting and never see a "Completa los
datos fiscales" banner on `/dashboard`.

The follow-up restores the four-step wizard from sprint 3.10
**without giving up the soft-creation envelope from
sprint 3.11**: every step still allows submission with only
`name` populated, via a secondary "Saltar y crear" button
that POSTs whatever has been captured so far. The Zod schema
(from sprint 3.11) already marks every field except `name`
as `.optional()`, the backend already coerces empty fiscal
fields to `None` per ADR-0034, and the shadcn primitives
(`Select`, `Checkbox`, `Tooltip`, `DatePicker`) stayed
installed when 3.11 stripped the route's body — no contract
changes, no migration, no ADR.

### Scope

- Restore the four-step layout at
  `apps/web/src/routes/tenants/new.tsx`:
  - Paso 1 — Identidad (`name` *required*, `ruc` optional).
  - Paso 2 — Régimen fiscal (`regime`, `municipality`,
    `is_withholder`, all optional).
  - Paso 3 — Autorización DGI (`number`, `valid_from`,
    `valid_to`, all optional).
  - Paso 4 — Dirección y resumen (`fiscal_address` optional
    + Revisión card).
- Restore the sprint-3.10 polish: `RequiredMark` only on
  `name`, `onTouched` mode, `attemptedSteps`-gated errors,
  sectioned Revisión card with Badge for Retenedor and
  Spanish-formatted Vigencia.
- Add a secondary "Saltar y crear" button to every step's
  `<CardFooter>`. Clicking it bypasses the per-step
  `trigger()` gate and runs `handleSubmit(onSubmit)` with
  whatever the form currently holds.
- On step 1, "Saltar y crear" is disabled until `name` is
  non-empty (the only required field). On every other step
  it is always enabled.
- Step 4 keeps the primary "Crear empresa" submit button;
  the "Continuar" / "Saltar y crear" pair appears on steps
  1-3.
- Submission semantics are unchanged from sprint 3.11: the
  backend's empty-string coercion + Optional VOs accept the
  payload as-is, and the `<Alert>` banner on `/dashboard`
  continues to surface for tenants with NULL `ruc` /
  `fiscal_address`.

### Out of scope (non-goals)

- No backend changes. `CreateTenantRequest`, `CreateTenant`,
  the `Tenant` aggregate, and the value objects keep the
  Optional shape introduced in 3.11.
- No new value objects or DGI validation. Optional fields
  stay strict only when supplied; empty strings are still
  coerced to `None` server-side.
- No "Editar empresa" implementation — that route stays a
  stub per 3.11.
- No new ADR. The change extends the existing
  `tenants-new-form` capability under the ADR-0034 (soft
  creation) + ADR-0009 (shadcn stack) envelope.
- No frontend slice rename and no rename of the route from
  `/tenants/new`.

## Sprint follow-up — Force empresa picker on every session (sprint 3.13, 2026-05-28)

### Motivation

Operator feedback after sprint 3.11: the post-login destination
defaults to `/dashboard`, leaving the empresa picker tucked behind
the sidebar `TenantSwitcher` chip. New operators (or operators
switching back to a workstation they have not signed into this
session) regularly miss the chip on day one, do not realise they
are looking at the empresa they happened to land on, and either
mis-attribute data or fail to find the empresa they actually want.

### Scope

A session-scoped picker-confirmed flag now lives in
`sessionStorage["nica-erp:picker-confirmed"]`. Until it is set —
which happens only on a successful `useSwitchTenantMutation`,
including the wizard's `/tenants/new` → switch → dashboard path —
the route guard redirects every authenticated route (other than the
TENANT_EXEMPT set) to `/tenants`. The picker route itself was
rewritten into the spec's grid: search input, "+ Nueva empresa"
button on the right, one card per empresa with an initials avatar,
role badge, and a pending-invitations subtitle. Clicking a card
runs the switch, flips the flag, and navigates to `/dashboard`.

The sidebar's `TenantSwitcher` gained a persistent "Cambiar
empresa" affordance — even for single-empresa operators — that
clears the flag and navigates to `/tenants`. `useLogoutMutation`
clears the flag as part of its settled handler so a fresh login
re-forces the picker.

### Verifiable outcome

Manual smoke per `openspec/changes/force-tenant-picker-and-back-link/tasks.md`
§7. Automated: extended `tests/unit/lib/route-guard.test.ts` and
new `tests/unit/routes/tenants-index.test.tsx`. `pnpm -C apps/web
test|typecheck|lint` all green.

### Non-goals

- No auto-skip for single-empresa operators. They still see the
  picker; one card is one click.
- No cross-session memory of the last picked empresa. The flag is
  session-scoped on purpose so a fresh tab forces the choice.
- No logo / branding field on cards. Initials avatar is enough.

## Sprint follow-up — Empresa section + account scope split (sprint 3.14, 2026-05-28)

### Motivation

Operator feedback after sprint 3.13: the empresa management surface
(members + invitations) was unreachable from the sidebar — it lived
under `/tenants/$id/members`, a route only navigable from the picker.
At the same time, the "Cuenta" page rendered inside the dashboard
chrome, which conflated user-scoped settings (profile, locale) with
empresa-scoped settings.

### Scope

A two-level `Empresa` section in the sidebar replaces the flat
`Tenants` entry. Children: `Vista general` (`/empresa`), `Usuarios`
(`/empresa/users`), `Configuración` (`/empresa/settings`). The
sidebar primitives gained `SidebarMenuSub`, `SidebarMenuSubItem`,
`SidebarMenuSubButton`, and a `useSidebarSection(key)` hook that
persists per-section open/closed state under
`localStorage["nica-erp:sidebar-<key>-open"]`.

The legacy `/tenants/$id/members` route now redirects to
`/empresa/users`. The legacy `/empresa/editar` route redirects to
`/empresa/settings`.

The account chrome split: `/account` no longer uses `AppShell`. A
new `IdentityLayout` renders only a top bar with `← Volver` (reads
`sessionStorage["nica-erp:last-app-route"]`, set by AppShell on
every mount) and the `TenantSwitcher` chip. The three identity
cards (Perfil / Empresa activa / Permisos) are unchanged.

### Naming convention

Routes are English; user-visible labels stay Spanish. So
`/empresa/users` renders the `Usuarios` sidebar label, and
`/empresa/settings` renders `Configuración`. This matches the
existing convention across the rest of the SPA (`/login`,
`/signup`, `/dashboard`, etc.) and the project's Spanish-UI rule.

### Verifiable outcome

Manual smoke per `openspec/changes/restructure-sidebar-empresa-and-account/tasks.md`
§8. Automated: `tests/unit/components/app-sidebar/app-sidebar.test.tsx`,
`tests/unit/components/app-sidebar/sidebar-context.test.tsx`
(extended), `tests/unit/routes/empresa/index.test.tsx`,
`tests/unit/routes/empresa/users.test.tsx`,
`tests/unit/routes/account.test.tsx` (rewritten for IdentityLayout).
`pnpm -C apps/web test|typecheck|lint` all green.

### Non-goals

- No wired fiscal editor — `/empresa/settings` ships as a
  "Próximamente" placeholder. The `useUpdateTenantMutation` hook
  is in place so the editor lift is a follow-up sprint.
- No per-user permission overrides. The backend's
  `tenants-http/spec.md` mentions overrides for tenant admins, but
  the API has no endpoint and the SPA no surface yet.
- No audit log.

### Backend gap — per-user permission overrides

The spec under `openspec/changes/restructure-sidebar-empresa-and-account/specs/tenants-http/spec.md`
calls for per-user permission overrides (a tenant admin opt-in
that grants/revokes specific actions to a specific operator). The
gap is **specified but not implemented** by this sprint; the
backend has no `PATCH /v1/tenants/{tenantId}/members/{userId}/permissions`
endpoint and the SPA has no UI. Document only — no follow-up
ticket yet.

### Backend gap — `POST /v1/invitations/accept` GUC

The new token-body endpoint is missing the per-request
`SET LOCAL nica_erp.tenant_id` GUC that the rest of the tenants
HTTP routes rely on. Tracked under
`openspec/changes/test-backfill-and-e2e-tooling/tasks.md` §3.2 —
the integration test that pins the regression is part of that
backfill, not this sprint.

## Sprint follow-up — Test backfill closure note (2026-05-28)

### Achieved coverage

The test-backfill landed in two waves: the schema and use-case
layer in sprint 3.5, and the feature-level hook + component layer
in this sprint. Where the original tasks asked for one file per
hook, we condensed to one consolidated suite per domain — the file
count differs but the assertion surface matches.

Backend (`apps/api`):
- Domain + application use cases: ten files covering happy path
  and every documented error branch (RUC dup, expired token,
  owner protection, role validation, idempotent re-submission).
- Repositories: testcontainer fixtures for tenant, membership,
  invitation, JWT.
- HTTP: tenant lifecycle e2e green; per-route × per-status
  matrix backfill (§2.5-§2.7) and the public-accept GUC fix
  remain open.

Frontend (`apps/web`):
- Schemas: auth + tenants, every documented branch.
- Hooks: complete coverage of auth (11 hooks) and tenants (10
  hooks + queryKey shape).
- Components: app-shell, app-sidebar (collapse + per-section
  persistence + active-state + Empresa parent), dashboard
  (four cards).
- Routes: confirm, welcome, onboarding, tenants/new, tenants
  (picker), account, dashboard, empresa/index, empresa/users.
- Route guard: every probe (welcome, onboarding, picker,
  active-tenant, exempt set).

### Known open follow-ups

The §2.5-§2.7 HTTP test backfill and the §9 Playwright suite are
the major remaining gaps. They are tracked in
`openspec/changes/test-backfill-and-e2e-tooling/tasks.md`. The
auth Playwright spec (§9.1) is green; the tenant + member
lifecycle specs need the per-context-fixtures + auth helpers
landed in §8.3 before they unblock.

## Sprint follow-up — Invited-user onboarding lands session-ready (sprint 3.15, 2026-05-31)

The invited-user happy path captured during a pilot run still
asks the user to re-type the password they just typed seconds
ago on `/signup`, and then bounces them through the empresa
picker even though they only have one membership. The terminal
log made both detours explicit:

```
POST /v1/auth/register      201
POST /v1/auth/confirm-signup 204    # no tokens
POST /v1/auth/login          200    # forced re-entry of credentials
POST /v1/invitations/accept  200    # membership created
GET  /v1/tenants/<id>/invitations 403   # JWT lacks active_tenant
POST /v1/tenants/<id>/switch 200    # JWT finally has active_tenant
```

Both detours are redundant: at the moment each endpoint runs,
the backend already has everything it needs to leave the caller
in the next session state. Sprint 3.15 closes the gap on the
two endpoints, gated by [ADR-0035](../adr/0035-onboarding-endpoints-return-session.md).

Sprint 3.15 is a contract enrichment on two endpoints + the
matching frontend wiring + the E2E coverage the original sprint
left as `.fixme()`. No new bounded context, no DB migration, no
infra change.

### Scope

- `POST /v1/auth/confirm-signup` accepts an optional `password`
  in its body. When present, the use case confirms the code and
  calls `IdentityProvider.authenticate` in the same transaction,
  returning `200 OK` with `{ access_token, refresh_token, id_token }`.
  When absent, the endpoint keeps its current `204 No Content`
  shape so a bare `confirm` (e.g. after a `/confirm` page refresh
  that lost the password from router state) still works.
- `POST /v1/invitations/accept` accepts an optional `refresh_token`
  in its body. After persisting the `Membership`, if the caller's
  validated `CurrentUserContext` has no prior `custom:active_tenant`,
  the use case calls `IdentityProvider.update_active_tenant`
  followed by `IdentityProvider.refresh(refresh_token)` and
  returns the new bundle inside an optional `tokens` field. When
  the caller already had an `active_tenant`, the existing response
  shape is preserved and no token rotation happens (a veteran
  user joining a second empresa stays inside the empresa they
  were working on — see [ADR-0035](../adr/0035-onboarding-endpoints-return-session.md)
  Alternative C).
- `apps/web/src/routes/signup.tsx` passes the typed password to
  `/confirm` via TanStack Router state (in-memory, lost on hard
  refresh — that is the documented fallback).
- `apps/web/src/routes/confirm.tsx` reads `password` from router
  state. When present, it posts to `confirm-signup` with the
  password and calls `storeTokens()` + invalidates `meQueryKey`
  on success; when absent it falls back to the current `/login`
  navigation.
- `apps/web/src/features/tenants/api/endpoints.ts` posts
  `{ token, refresh_token }` to `/v1/invitations/accept` and, on
  responses that include `tokens`, calls `storeTokens()` before
  invalidating `meQueryKey` and `myTenantsKey`. The route guard
  then lets the user through directly to `/dashboard` without
  the empresa picker detour.

### Out of scope

- No change to `POST /v1/tenants` (first-empresa creation) — it
  keeps its current shape; the same user flow there ends with an
  explicit `POST /v1/tenants/{id}/switch` and the established
  empresa-picker UX.
- No change to `POST /v1/auth/password/reset` — landing back at
  `/login` after a reset is the documented behaviour.
- No persistence of the typed password beyond TanStack Router
  in-memory state. `sessionStorage` and `localStorage` are off
  the table per the JS-memory-only token policy in
  [`docs/06-security-model.md` §Refresh and revocation](../06-security-model.md#refresh-and-revocation).

### Gate tests

- Backend integration: `confirm-signup` returns tokens when the
  body includes a valid password and returns `204` when it does
  not. Both branches assert no side effect on the user aggregate
  beyond the existing confirmed-signup expectations.
- Backend integration: `accept-invitation` returns `tokens` when
  the caller had no prior `active_tenant` and the new JWT
  contains `custom:active_tenant=<invited tenant>`. The same
  endpoint omits `tokens` when the caller already had an
  `active_tenant`, and `GET /v1/me` after the call shows the
  pre-existing empresa unchanged.
- Frontend E2E
  (`apps/web/tests/e2e/invitation-accept.spec.ts`): the
  invited-new-user happy path runs end to end — owner invites,
  invitee opens the email link, previews, signs up, confirms,
  lands on `/dashboard` of the invited empresa without re-typing
  credentials and without passing through the empresa picker.
  The current `.fixme()` marker is removed.
- Frontend E2E (new): veteran user accepting an invitation to a
  second empresa stays inside their original empresa after the
  accept call returns. The picker is **not** displayed.
- Frontend E2E (new): refreshing `/confirm` between `/signup`
  and code entry loses the password from router state. The
  fallback path navigates to `/login` and the user types their
  credentials there. No console error, no broken intermediate
  state.

### References

- [ADR-0035](../adr/0035-onboarding-endpoints-return-session.md) —
  the policy for terminal onboarding endpoints.
- [ADR-0031](../adr/0031-invitation-token-transport.md) — hash
  fragment transport (unchanged; this sprint reuses the existing
  `/v1/invitations/accept` POST body shape).
- Sprint 02 §Endpoints — the `confirm-signup` endpoint owned by
  the `identity` context; this sprint extends its request body
  shape only.

## Sprint follow-up — fix identity-context wrong-input statuses (2026-06-03)

The 2026-06-03 audit found a second class of misclassified errors on
the public auth endpoints. The signup-OTP path, the password-reset
path, and the resend-cooldown path all surfaced the same response:
`401 application/problem+json` with `code: "auth.invalid_credentials"`.
That:

- collapsed three semantically distinct failures into one
  diagnostic — operators saw the same generic "credentials" copy
  for an OTP typo as for a wrong login;
- forced the SPA's 401 interceptor to carry a `__bearerAttached`
  discriminator (sprint 3.x follow-up earlier in this document) just
  so a wrong OTP on `/confirm` would not destroy the session and
  redirect to `/login`;
- left the `messageForProblem` registry entries that the frontend
  *already* shipped for the documented codes
  (`auth.invalid_confirmation_code`, `auth.reset_token_used`,
  `auth.reset_token_expired`) as dead code, because the backend never
  emitted them.

### Root cause

`InvalidCredentialsError` is the identity context's catch-all for
"the input did not match what the IdP expected." It was raised in
eight distinct call sites across `local.py` / `cognito.py` and every
one mapped to 401 in
`apps/api/src/contexts/identity/adapters/inbound/http/errors.py`. The
adapter even acknowledged the mismatch on the resend-cooldown branch
with a misleading comment claiming the HTTP adapter mapped it to 400
(it did not — the mapper produced 401).

### Scope

- Split `InvalidCredentialsError` into four typed application
  exceptions, one per wrong-input failure mode:
  - `InvalidConfirmationCodeError` (wrong / expired OTP).
  - `InvalidResetCodeError` (used / unknown / hash-mismatched reset
    code) and `ExpiredResetCodeError` (its subclass for the explicit
    TTL-elapsed case).
  - `ResendThrottledError(retry_after_seconds: int)` for the
    per-account resend cooldown.
- Raise the new types from both the local and Cognito IdP adapters
  at the relevant call sites. The Cognito adapter cannot read the
  real `retry_after_seconds` for `LimitExceededException`, so it
  uses a 60-second fallback that matches the AWS default; the local
  adapter computes the actual remaining cooldown.
- Translate each new type in the HTTP error mapper:
  - `InvalidConfirmationCodeError` → `400 auth.invalid_confirmation_code`.
  - `InvalidResetCodeError` → `410 auth.reset_token_used`.
  - `ExpiredResetCodeError` → `410 auth.reset_token_expired`
    (registered FIRST so the subclass wins).
  - `ResendThrottledError` → `429 auth.resend_throttled` with a
    `Retry-After: <seconds>` header and `retry_after_seconds` in the
    body.
- Login keeps its 401 surface for wrong credentials — the
  `__bearerAttached` discriminator stays useful for that one
  remaining case.
- Add `auth.resend_throttled` to the frontend `messageForProblem`
  registry (Spanish copy: "Espera unos segundos antes de pedir otro
  código.") and to `KNOWN_AUTH_PROBLEM_CODES`. The other three
  codes were already in the registry.
- Extend the OpenAPI `responses=` hints on `/v1/auth/confirm-signup`,
  `/v1/auth/password/reset`, and `/v1/auth/resend-code` so the
  regenerated `apps/web/src/api/schema.d.ts` advertises the new
  statuses.

### Verifiable outcome

- Backend e2e: `POST /v1/auth/confirm-signup` with a wrong OTP →
  `400 application/problem+json` with `code:
  "auth.invalid_confirmation_code"`. `POST /v1/auth/password/reset`
  reused → `410 auth.reset_token_used`. A second `POST
  /v1/auth/resend-code` within the cooldown window → `429
  auth.resend_throttled` with `Retry-After` header and
  `retry_after_seconds` body field.
- Backend e2e regression: `POST /v1/auth/login` with a wrong
  password still returns `401 auth.invalid_credentials`; `GET /v1/me`
  with no bearer still returns `401 auth.invalid_credentials`.
- Backend unit / integration tests for the local and Cognito
  adapters assert the new exception types at the raise sites and the
  new `(status, code, title)` triples at the mapping layer.
- Frontend unit test asserts `messageForProblem({ code:
  "auth.resend_throttled" })` returns the documented Spanish copy
  and that `KNOWN_AUTH_PROBLEM_CODES` includes the new entry.

### Non-goals

- No change to login's 401 contract — the `__bearerAttached` flag in
  the 401 interceptor still discriminates a "wrong login credentials"
  401 from a bearer-attached session-lost 401.
- No new `RateLimitedError` base class. The resend cooldown is the
  only resend-throttle site today; login-throttle has its own typed
  error already.
- No new ADR. The HTTP statuses move within the documented 4xx
  envelope, and the problem codes were already promised by the
  `frontend-auth-error-feedback` capability. This is implementation
  realignment, not an architectural decision.
- No interceptor refactor. The `__bearerAttached` flag stays as the
  safer default in case a future endpoint adds a 401 surface where
  no bearer is attached.
