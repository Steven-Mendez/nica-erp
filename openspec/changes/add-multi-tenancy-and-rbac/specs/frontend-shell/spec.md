## ADDED Requirements

### Requirement: `features/tenants/` slice owns the tenant UI surface

`apps/web/src/features/tenants/` SHALL contain the slice's
schemas, hooks, and components. Per
[`docs/09-frontend.md`](../../../../docs/09-frontend.md) §No
cross-feature imports, no other `features/<x>/` directory MAY
import from `features/tenants/`. Within-slice imports SHALL use
relative paths (`./api/useMyTenants`), not the `@/features/...`
alias.

The slice SHALL expose:

- `schemas/` — `createTenantSchema`, `updateTenantSchema`,
  `inviteMemberSchema`, `updateMemberRoleSchema` (Zod).
- `api/` — TanStack Query hooks: `useMyTenants`, `useTenant`,
  `useCreateTenant`, `useUpdateTenant`, `useMembers`,
  `useInviteMember`, `useRemoveMember`, `useUpdateMemberRole`,
  `useInvitations`, `useCancelInvitation`,
  `useAcceptInvitation`, `useSwitchTenant`.
- `components/` (optional) — feature-private UI primitives;
  shared UI lives in `src/components/`.

#### Scenario: ESLint blocks a cross-slice import

- **GIVEN** a candidate change adding `import { foo } from
  "@/features/tenants/..."` inside `features/auth/`
- **WHEN** `pnpm lint` runs
- **THEN** the ESLint `no-restricted-imports` rule SHALL flag the
  import and the command SHALL exit non-zero

### Requirement: New routes cover the tenant lifecycle UX

`apps/web/src/router.ts` SHALL register four new routes:

- `/tenants/new` — create-tenant form.
- `/tenants` — list of memberships (each card links to its tenant
  workspace; the active one is marked).
- `/tenants/$tenantId/members` — members + invitations management.
- `/invitations/$token/accept` — public route that, on mount,
  posts to `/v1/invitations/{token}/accept` and on success
  redirects to `/tenants`.

The first three routes are gated by the auth-required posture
(redirect to `/login` if no access token is present). The fourth is
public — accessible without an access token; the SPA prompts to log
in if not authenticated.

#### Scenario: Authenticated route enforces redirect

- **GIVEN** the SPA has no access token in memory
- **WHEN** the user navigates directly to `/tenants/new`
- **THEN** the router SHALL redirect to `/login`

### Requirement: `Topbar` hosts the `TenantSwitcher`

`apps/web/src/components/topbar/Topbar.tsx` SHALL render at the
top of `__root.tsx`'s layout whenever the in-memory
`tokenStore.getAccessToken()` returns non-null AND
`useCurrentUser().data?.role` is non-null (an active tenant
context is present). The Topbar SHALL contain `TenantSwitcher`
(a dropdown listing the user's memberships, marking the active
one) and a logout button.

`TenantSwitcher.onChange(tenantId)` SHALL:

1. Call `POST /v1/tenants/{tenantId}/switch` with the in-memory
   `refresh_token` in the body.
2. On success, call `tokenStore.setTokens(...)` with the returned
   bundle.
3. Call `queryClient.clear()` to evict all query caches keyed to
   the old tenant.
4. Call `router.invalidate()` to force re-render with fresh data.

On failure (e.g. 403 because membership was revoked between the
last `/v1/me` call and the switch), the switcher SHALL surface a
toast and leave the previous tenant active.

#### Scenario: Successful switch clears caches and invalidates router

- **WHEN** `TenantSwitcher.onChange(<T>)` resolves successfully
- **THEN** `tokenStore.getAccessToken()` SHALL return the new
  access token, `queryClient.clear()` SHALL have been called
  exactly once, and `router.invalidate()` SHALL have been called
  exactly once

### Requirement: `useHasPermission` is shared infra

`apps/web/src/api/useHasPermission.ts` SHALL export a hook
`useHasPermission(code: string): boolean` that reads the
`useCurrentUser()` query (`/v1/me`) and returns
`true` iff `data?.permissions?.includes(code)`. When the query is
pending or `data` is undefined, the hook SHALL return `false` so
disabled buttons stay disabled rather than flicker enabled.

The hook SHALL be importable from any feature slice (it lives in
`src/api/`, which is shared infra per the no-cross-feature rule).

#### Scenario: Pending query returns false

- **GIVEN** the `/v1/me` query is in `pending` state
- **WHEN** `useHasPermission("tenant:write")` is called
- **THEN** the hook SHALL return `false`

#### Scenario: Loaded admin returns true for `tenant:write`

- **GIVEN** `/v1/me` has resolved with `permissions: ["tenant:read",
  "tenant:write", ...]`
- **WHEN** `useHasPermission("tenant:write")` is called
- **THEN** the hook SHALL return `true`

### Requirement: TanStack Query keys are namespaced per tenant

Every hook in `features/tenants/api/` whose data is tenant-scoped
SHALL include the active tenant id in its query key — e.g.
`["tenant", tenantId, "members"]` rather than `["members", tenantId]`.
This keeps the `queryClient.clear()` call in `TenantSwitcher`
unnecessary for correctness (no key collisions between tenants),
but the call remains as a belt-and-suspenders defence per the
sprint doc.

#### Scenario: Query keys carry the tenant id

- **GIVEN** the `useMembers(tenantId)` hook
- **WHEN** TanStack Query records the key
- **THEN** the key tuple SHALL start with `["tenant", tenantId, ...]`
