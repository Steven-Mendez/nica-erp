# frontend-tenant-cache-isolation Specification

## Purpose
TBD - created by archiving change harden-tenant-isolation-and-errors. Update Purpose after archive.
## Requirements
### Requirement: Logout clears the entire React Query cache

The logout mutation SHALL invoke `queryClient.clear()` in its `onSettled` callback, after the in-memory token store has been cleared and after the picker-confirmed flag has been reset. The order of operations MUST be:

1. Clear the token store.
2. Clear the picker-confirmed flag.
3. Call `queryClient.clear()`.

This applies regardless of whether the `POST /v1/auth/logout` request
succeeded or failed.

#### Scenario: Logout success clears the cache

- **WHEN** an authenticated operator triggers `useLogoutMutation` and
  the backend responds `204 No Content`
- **THEN** every query in the React Query cache is removed before the
  router navigates to `/login`

#### Scenario: Logout network failure still clears the cache

- **WHEN** an authenticated operator triggers `useLogoutMutation` and
  the request fails with a network error
- **THEN** the cache is cleared, the token store is empty, and the
  router still navigates to `/login`

#### Scenario: Login as a different operator does not show the previous operator's data

- **WHEN** operator A logs out and operator B logs in on the same
  browser without a hard reload
- **THEN** the `/empresa/usuarios` table renders only operator B's
  members and there is no transient frame showing operator A's data

### Requirement: Per-tenant queries refuse to fire when their tenant id is no longer active

Every per-tenant TanStack Query hook MUST gate its `enabled` flag on the current `me.active_tenant`. Specifically, the hooks under `apps/web/src/features/tenants/api/hooks.ts` whose query key starts with `["tenant", <id>, …]` — `useTenantQuery`, `useMembersQuery`, and `useInvitationsQuery` — SHALL gate their
`enabled` flag on **both** of:

1. The `tenantId` argument is a non-empty string.
2. The `tenantId` argument equals the current
   `useMeQuery().data?.active_tenant`.

When condition 2 is false, the hook MUST NOT issue a request, MUST
NOT throw, and MUST surface the disabled state to the caller (no data,
`isLoading: false`, no `error`).

#### Scenario: Stale tenant id during a switch is ignored

- **WHEN** a component captures `tenantId = "tenant-a"` and renders
  `useMembersQuery("tenant-a")` while `me.active_tenant` has just
  flipped to `"tenant-b"`
- **THEN** the hook does not issue `GET /v1/tenants/tenant-a/members`,
  even briefly

#### Scenario: Matching tenant id behaves unchanged

- **WHEN** a component renders `useMembersQuery(me.active_tenant)`
  with a non-empty active tenant
- **THEN** the hook issues `GET /v1/tenants/{active_tenant}/members`
  exactly as before this change

#### Scenario: Empty tenant id remains a no-op

- **WHEN** a component renders `useMembersQuery("")`
- **THEN** the hook does not issue any request, matching pre-change
  behavior

### Requirement: Cache isolation is verified by integration tests under tests/integration

Integration tests SHALL exist under `apps/web/tests/integration/`
covering at least:

- Logout-then-login-as-other-operator does not render any data from
  the previous operator.
- A component that captured an old tenant id during a tenant switch
  does not produce a request to the old tenant id.

The tests MUST use MSW to simulate the backend and MUST mirror the
project's existing integration test layout (under
`apps/web/tests/integration/`, not co-located).

#### Scenario: Identity-rotation integration test exists

- **WHEN** the test suite under `apps/web/tests/integration/` is
  enumerated
- **THEN** at least one file covers the cross-identity cache-isolation
  contract above, and the suite runs in CI as part of the standard
  Vitest invocation

