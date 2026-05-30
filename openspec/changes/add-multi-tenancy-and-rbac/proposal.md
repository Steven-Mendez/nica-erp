## Why

Sprint 03 introduces the project's **second bounded context** (`tenants`)
and the two cross-cutting patterns every subsequent sprint reuses:
**per-table Postgres RLS for tenant-scoped tables** and **per-endpoint
RBAC enforcement via `require(...)`**. After this change, sprints 04-08
add tables and endpoints by composing both patterns without touching
middleware. Reference:
[`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md),
[`docs/05-multi-tenancy.md`](../../../docs/05-multi-tenancy.md),
[`docs/06-security-model.md`](../../../docs/06-security-model.md),
[ADR-0002](../../../docs/adr/0002-postgres-rls.md),
[ADR-0022](../../../docs/adr/0022-rbac-model.md).

This change converts the empty `tenants` placeholder shipped by
migration 0001 into a real fiscal aggregate, introduces `tenant_members`
and `invitations`, materialises the `permissions` / `role_permissions`
catalog, and wires the `tenant_middleware` that issues
`SET LOCAL app.tenant_id` and `SET LOCAL app.current_user_id` per
request — without which sprint 04 cannot persist a single product row
inside a tenant.

## What Changes

### Backend — `tenants` bounded context

- New context `apps/api/src/contexts/tenants/` with the canonical
  hexagonal layout (`domain/`, `application/`, `adapters/`).
- **Domain**: `Tenant` aggregate (`id`, `name`, `ruc`, `regime`,
  `municipality`, `authorization_dgi`, `fiscal_address`,
  `is_withholder`, `status`, timestamps); `Membership` entity
  (`user_id`, `tenant_id`, `role`, `status`, `joined_at`,
  `removed_at`); `Invitation` entity (`token_hash`, `tenant_id`,
  `email`, `proposed_role`, `expires_at`, `status`, `cancelled_at`).
  Value objects: `Ruc` (Nicaragua RUC validation), `Municipality`
  (extensible enum), `Regime` (`general` / `simplified`),
  `AuthorizationDgi` (number + validity dates), `Role` (enum:
  `owner`, `admin`, `accountant`, `salesperson`, `viewer`).
  Events: `TenantCreated v1`, `MemberInvited v1`, `MemberJoined v1`,
  `MemberRemoved v1`, `InvitationCancelled v1`, `MemberRoleChanged v1`.
- **Application use cases** (9): `CreateTenant`, `GetMyTenants`,
  `GetTenant`, `UpdateTenant`, `InviteMember`, `AcceptInvitation`,
  `CancelInvitation`, `RemoveMember`, `SwitchActiveTenant`.
  `SwitchActiveTenant` invokes
  `IdentityProvider.update_active_tenant(...)` and returns a fresh
  `Identity` (access/refresh/id tokens whose `custom:active_tenant`
  matches the new tenant).
- **Outbound ports**: `TenantRepository`, `MembershipRepository`,
  `InvitationRepository`, `InvitationTokenGenerator` (signed token
  factory + verifier), `EmailSender` (reused from sprint 02 for
  invitation emails).

### Backend — RBAC

- New module `apps/api/src/shared_kernel/permissions/` with:
  - `catalog.py` — `Permission` dataclass + `TENANT_PERMISSIONS`
    tuple + `ROLES` tuple + `DEFAULT_ROLE_PERMISSIONS` mapping. The
    canonical Nicaragua roles list (`viewer`, `salesperson`,
    `accountant`, `admin`, `owner`) lives here as the **source of
    truth**.
  - `Actor` dataclass (`user_id`, `tenant_id`, `role`, `permissions:
    frozenset[str]`).
  - `cache.py` — process-local TTL cache over `(role → frozenset)`
    with TTL = 60 s.
- `bootstrap/dependencies.py` gains `current_actor(...)` (resolves
  `Actor` from `CurrentUserContext` + `TenantContext` + a DB lookup)
  and `require(*codes)` (FastAPI dependency that 403s on a missing
  code).
- `ForbiddenError` → 403 `application/problem+json` with `type=missing-permission`
  and extension `missing: [...]`
  ([ADR-0015](../../../docs/adr/0015-rfc7807-errors.md)).

### Backend — multi-tenancy + RLS

- New middleware `TenantMiddleware` (registered **after** `AuthMiddleware`
  in `bootstrap/api.py`):
  1. Reads `custom:active_tenant` from `CurrentUserContext`.
  2. If empty and the route is not in `NO_TENANT_REQUIRED` → 403
     `tenant.required` (already handled by `AuthMiddleware`; this
     middleware does not duplicate the check).
  3. If set → validates that an active `tenant_members` row exists for
     `(user_id, tenant_id)`; otherwise 403 `tenant.not_member`.
  4. Calls `TenantContext.set(tenant_id)`.
- `_RequestUnitOfWork` (sprint 02) gains a hook that, on the **outer**
  `begin()`, executes `SET LOCAL app.tenant_id = '<uuid>'` and
  `SET LOCAL app.current_user_id = '<uuid>'` before yielding the
  session. The hook is a no-op for the reentrant inner `begin()`
  branch — only the outer transaction sets the GUCs.

### Backend — HTTP layer

- New `/v1/tenants` router:
  - `POST /v1/tenants` — body `{name, ruc, regime, municipality,
    authorization_dgi, fiscal_address, is_withholder}`; creates the
    tenant and the owner membership in the same UoW; idempotent on
    `(actor.user_id, name)`. Allowed without an active tenant
    (already in `NO_TENANT_REQUIRED` from sprint 02).
  - `GET /v1/tenants/me` — list memberships of the current user
    (uses the special `tenant_members_self` policy).
  - `GET /v1/tenants/{id}` — get tenant fiscal metadata
    (`tenant:read`).
  - `PATCH /v1/tenants/{id}` — update mutable fiscal metadata
    (`tenant:write`).
  - `POST /v1/tenants/{id}/switch` — calls
    `SwitchActiveTenant`; returns a fresh `Identity` (200) with the
    new JWT.
  - `GET /v1/tenants/{id}/members` (`members:read`),
    `PATCH /v1/tenants/{id}/members/{user_id}` (`members:update-role`),
    `DELETE /v1/tenants/{id}/members/{user_id}` (`members:remove`).
  - `GET /v1/tenants/{id}/invitations` (`members:read`),
    `POST /v1/tenants/{id}/invitations` (`members:invite`),
    `DELETE /v1/tenants/{id}/invitations/{invitation_id}` (`members:invite`).
- New `/v1/invitations/{token}/accept` route (public; already
  allowlisted in sprint 02).
- `GET /v1/me` is **modified** to additionally return `role: string |
  null` and `permissions: string[]` for the active tenant (null + `[]`
  when no active tenant is set).

### Backend — identity-provider deltas

- `IdentityProviderLocal.update_active_tenant` already exists from
  sprint 02; this change adds a **regression test** that verifies the
  new JWT minted by `authenticate()` after the attribute update
  carries the new `custom:active_tenant` claim, and that
  `SwitchActiveTenant`'s returned `Identity` does the same.
- `IdentityProviderCognito.update_active_tenant` already exists; this
  change verifies (via a mocked client test) that `AdminUpdateUserAttributes`
  is called exactly once with `Name="custom:active_tenant"` and the
  new value.

### Backend — migration 0003

- `ALTER TABLE tenants` adds fiscal columns: `ruc TEXT UNIQUE NOT NULL`,
  `regime TEXT NOT NULL CHECK (regime IN ('general','simplified'))`,
  `municipality TEXT NOT NULL`, `authorization_dgi_number TEXT`,
  `authorization_dgi_valid_from DATE`, `authorization_dgi_valid_to DATE`,
  `fiscal_address TEXT NOT NULL`, `is_withholder BOOLEAN NOT NULL DEFAULT FALSE`,
  `status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('provisioning','active','suspended','purged'))`,
  `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. `tenants` has **no
  RLS** (global catalog per ADR-0002).
- `CREATE TABLE tenant_members` with the standard columns
  (`id`, `user_id`, `tenant_id`, `role`, `status`, `joined_at`,
  `removed_at`); RLS with the **special** policy
  `USING (user_id = current_setting('app.current_user_id', true)::uuid OR
   tenant_id = current_setting('app.tenant_id', true)::uuid)` and
  `WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)`.
  Single-owner constraint: `CREATE UNIQUE INDEX uq_tenant_members_owner
  ON tenant_members(tenant_id) WHERE role='owner' AND status='active'`.
- `CREATE TABLE invitations` with `id`, `tenant_id`, `email CITEXT`,
  `proposed_role TEXT`, `token_hash TEXT UNIQUE`, `expires_at`,
  `status`, `cancelled_at`, `created_at`. RLS with the canonical
  per-tenant policy (`USING` + `WITH CHECK` on `app.tenant_id`).
- `CREATE TABLE permissions` (`code PK`, `resource`, `action`,
  `scope` CHECK `IN ('own','all','na')`, `description`); no RLS.
- `CREATE TABLE role_permissions` (`role`, `permission` FK,
  composite PK); no RLS.
- **Seed**: the migration imports `shared_kernel.permissions.catalog`
  and inserts `TENANT_PERMISSIONS` and `DEFAULT_ROLE_PERMISSIONS`
  with `ON CONFLICT DO NOTHING`, so sprints 04-08 append without
  pre-clearing.

### Frontend — tenant slice

- New `apps/web/src/features/tenants/` slice with:
  - Zod schemas: `createTenantSchema`, `updateTenantSchema`,
    `inviteMemberSchema`.
  - Hooks under `features/tenants/api/`: `useMyTenants`,
    `useTenant`, `useCreateTenant`, `useUpdateTenant`,
    `useMembers`, `useInviteMember`, `useRemoveMember`,
    `useUpdateMemberRole`, `useInvitations`, `useCancelInvitation`,
    `useAcceptInvitation`, `useSwitchTenant`.
- New routes under `apps/web/src/routes/`: `/tenants/new`,
  `/tenants/index` (= list memberships), `/tenants/$tenantId/members`,
  `/invitations/$token/accept`.
- New shared `Topbar` component under `apps/web/src/components/topbar/`
  containing `TenantSwitcher`. The switcher calls `POST /v1/tenants/{id}/switch`,
  stores the returned tokens via `tokenStore.setTokens(...)`, runs
  `queryClient.clear()`, and `router.invalidate()`. The Topbar is
  rendered by the root route layout when `CurrentUser.activeTenant`
  is set.
- The `currentUser` query (`/v1/me`) gains `role` and `permissions`;
  a small `useHasPermission(code)` helper lives in `src/api/` (shared
  infra) so any slice can gate UI consistently.

### Bootstrap wiring

- `bootstrap/api.py` registers `TenantMiddleware` between `AuthMiddleware`
  and the route layer (Starlette runs in reverse-add order: add Tenant
  before Auth so Auth is **inner** to Tenant? No — auth must run first,
  so `add_middleware(TenantMiddleware)` runs before
  `add_middleware(AuthMiddleware)` so Auth ends up outermost… see
  §Auth middleware order in design.md).
- `bootstrap/container.py` gains `build_tenants_use_cases()`,
  `build_tenant_repository()`, `build_membership_repository()`,
  `build_invitation_repository()`, `build_invitation_token_generator()`.
- `bootstrap/dependencies.py` gains `current_actor` and `require`.

### `domain-purity` import-linter contract

- Extended to cover `contexts.tenants.domain`: same prohibitions as
  `contexts.identity.domain` (no `sqlalchemy`, `fastapi`, `boto3`,
  cross-context, or own-context adapters/application imports).
- New contract for `shared_kernel.permissions.catalog`: MAY NOT
  import any `sqlalchemy`, `fastapi`, or `contexts.*` module.

## Capabilities

### New Capabilities

- `tenants-domain` — `Tenant`, `Membership`, `Invitation` aggregates;
  the five value objects; the six domain events; the single-owner
  invariant.
- `tenants-application` — the nine use cases, the four outbound ports,
  and the cross-context call to `IdentityProvider.update_active_tenant`
  from `SwitchActiveTenant`.
- `tenants-http` — `/v1/tenants/*` and `/v1/invitations/*` routers,
  per-endpoint `Depends(require(...))` wiring, request/response
  schemas, error mapping.
- `rbac-authorization` — `shared_kernel.permissions.catalog`, the
  `permissions` / `role_permissions` tables, `Actor`, `current_actor`,
  `require(*codes)`, TTL cache, `ForbiddenError`, the four sprint-gate
  tests (matrix, endpoint coverage, 403, 404).
- `multi-tenancy-rls` — the canonical per-table RLS pattern
  (`USING` + `WITH CHECK`), the `tenant_members_self` special policy,
  `TenantMiddleware`, `SET LOCAL app.tenant_id` /
  `SET LOCAL app.current_user_id` injection in `_RequestUnitOfWork`,
  the `forge_jwt` helper for isolation tests.

### Modified Capabilities

- `database-schema-bootstrap` — adds migration 0003 (ALTER `tenants`,
  CREATE `tenant_members` / `invitations` / `permissions` /
  `role_permissions`, RLS policies, single-owner index, catalog seed).
- `api-bootstrap` — registers `TenantMiddleware`, wires the new
  builders (`build_tenant_repository`, `build_membership_repository`,
  `build_invitation_repository`, `build_invitation_token_generator`),
  and exposes `current_actor` / `require` from
  `bootstrap/dependencies.py`.
- `identity-provider-cognito` — adds a contract test for
  `update_active_tenant` (one `AdminUpdateUserAttributes` call, no
  destructive side effects).
- `identity-provider-local` — adds a contract test confirming the
  new attribute is reflected in the next-minted JWT's
  `custom:active_tenant` claim, plus the `forge_jwt` testing helper
  in `contexts/identity/testing.py` (importable from tests only,
  blocked from productive adapters by import-linter).
- `identity-http` — extends `GET /v1/me` response with
  `role: string | null` and `permissions: string[]` for the
  active tenant.
- `frontend-shell` — adds the `features/tenants/` slice, the
  `Topbar` + `TenantSwitcher` component, the `/tenants/*` and
  `/invitations/$token/accept` routes, and the `useHasPermission`
  helper in `src/api/`.

## Impact

- **Affected code**: new `apps/api/src/contexts/tenants/` package; new
  `apps/api/src/shared_kernel/permissions/` module; new
  `apps/api/alembic/versions/0003_tenants_and_rbac.py`; modifications
  to `apps/api/src/bootstrap/{api,container,dependencies,settings}.py`,
  `apps/api/.importlinter`; new `apps/web/src/features/tenants/`,
  new `apps/web/src/components/topbar/`, new routes under
  `apps/web/src/routes/`.
- **Affected APIs**: ~13 new tenant routes plus the `/v1/me`
  response extension; one identity-provider port method
  (`update_active_tenant`) graduates from sprint 02's stub usage to
  full integration via `SwitchActiveTenant`.
- **Dependencies**: no new runtime dependencies (uses `pyjwt`,
  `bcrypt` from sprint 02 + existing `sqlalchemy` / `fastapi`).
- **Systems**: locally requires only the existing Postgres container;
  in AWS requires nothing new beyond what sprint 02 already
  provisioned (Cognito user-pool with `custom:active_tenant` attribute,
  IAM `cognito-idp:AdminUpdateUserAttributes`). **No new Terraform
  modules.**
- **Out of scope** (intentionally):
  - Sprints 04-08's tenant-scoped tables (each ships its own RLS via
    the canonical pattern established here).
  - The welcome / member-invited async notification worker (sprint 08
    consumes the `MemberInvited` event from the outbox).
  - Cross-tenant analytics, BYPASSRLS roles, super-admin tooling
    (post-MVP per [ADR-0002](../../../docs/adr/0002-postgres-rls.md)).
  - Tenant lifecycle transitions beyond `provisioning → active`
    (suspend / purge are operator runbooks per
    [ADR-0026](../../../docs/adr/0026-tenant-lifecycle.md)).
  - Tenant-editable custom roles, per-instance permissions
    ([ADR-0022](../../../docs/adr/0022-rbac-model.md)).
  - **AWS deploy**: deferred — the AWS account is in verification.
    The sprint's "post-deploy verification" steps remain unchecked in
    `tasks.md` and the sprint closure note explicitly defers them.
