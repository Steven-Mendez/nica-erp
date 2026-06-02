## Why

The post-sprint-03 QA audit surfaced two blocker-severity defects that
share a root cause: the SPA does not have a single, consistent strategy
for what happens when the **active identity changes** (logout, login as
a different operator) or when a **route loader throws** (403 from
`/v1/me`, Zod parse failure on a malformed payload, navigation to a
legacy URL).

1. `useLogoutMutation` in
   `apps/web/src/features/auth/api/hooks.ts:125-135` calls
   `qc.removeQueries({ queryKey: meQueryKey })` and clears the in-memory
   token store, but never invokes `queryClient.clear()`. The `["tenant",
   <id>, …]` member tables, invitation lists, and dashboard panels
   remain in cache. When the next operator logs in on the same browser
   the previous operator's empresa data renders for a frame until each
   query refetches — and any component that reads from cache without
   refetching (e.g. a list that mounts from `placeholderData`) shows
   the prior operator's rows indefinitely. This is a cross-tenant /
   cross-user data exposure, not just a UX nit.
2. The router is mounted in `apps/web/src/routes/__root.tsx` with no
   `errorComponent` and no `notFoundComponent`, and route loaders that
   throw (the `/v1/me` 403 for a user whose membership was removed
   mid-session, a Zod schema mismatch on a server-side change) bubble
   to TanStack Router's default boundary. The result is a white screen
   with `Something went wrong! GET /v1/me failed: 403` — the operator
   has no path back to `/login` or `/tenants` without manually editing
   the URL bar.

The audit's third recommendation under this heading — move the refresh
token from `sessionStorage` to `localStorage` so new tabs survive — is
explicitly out of scope. `apps/web/src/api/tokenStore.ts` documents the
sessionStorage placement as a deliberate XSS-blast-radius decision with
HttpOnly cookies + a BFF queued as the post-MVP follow-up. We are not
relitigating that here; the tab-portability story belongs in its own
change once the BFF is on the roadmap.

## What Changes

- Wire `queryClient.clear()` into the logout success path so cache
  state cannot survive an identity change on the same browser.
- Add a per-tenant cache-scope assertion: every existing query key
  under `["tenant", <id>, …]` MUST gate on the current `active_tenant`
  from `useMeQuery`, and the `enabled` guard MUST refuse to run when
  the tenant id read by the hook does not match `me.active_tenant`.
  This closes the race where a component captures the old tenant id
  during the `qc.clear() → invalidate(me)` window on switch.
- Add a root-level `errorComponent` and `notFoundComponent` on
  `rootRoute` (`apps/web/src/routes/__root.tsx`) that render the
  empty-AppShell Spanish-language fallback used elsewhere
  (`Próximamente`-style card). The fallback MUST distinguish
  `403 Forbidden`, `404 Not Found`, and generic runtime errors, and
  MUST offer a "Volver al inicio" link that routes to `/dashboard` if
  the operator is authenticated, otherwise `/login`.
- Add an `errorComponent` to the `AppShell` layout route so a 403 on
  a child loader (e.g. an empresa-scoped page the operator lost access
  to) degrades to the in-shell fallback instead of unmounting the
  shell.
- Add Vitest integration tests under
  `apps/web/tests/integration/` covering:
  - logout-then-login-as-other-user does not leak the prior operator's
    members table;
  - tenant switch race: a component that captured the old tenant id
    cannot fire a request with that stale id after `qc.clear()`;
  - `/v1/me` 403 renders the in-shell forbidden card, not a white
    screen;
  - a malformed `/v1/me` payload (Zod failure) renders the runtime
    fallback, not a white screen.

## Capabilities

### New Capabilities

- `frontend-tenant-cache-isolation`: query-client lifecycle rules — when
  caches MUST be cleared (logout, identity change), how per-tenant
  query keys gate on the active tenant, and the test surfaces that
  verify no cross-identity / cross-empresa leakage.
- `frontend-error-boundaries`: root and AppShell `errorComponent` /
  `notFoundComponent` contracts — what categories of failure render
  which Spanish fallback card, and how the operator is routed back to
  a safe page.

### Modified Capabilities

_(none — `frontend-shell` is unchanged; the token-store decision in
`apps/web/src/api/tokenStore.ts` is preserved as documented.)_

## Impact

- **Code:**
  - `apps/web/src/features/auth/api/hooks.ts` — `useLogoutMutation`
    gains `qc.clear()` on `onSettled`, after `clear()` and
    `clearPickerConfirmed()`.
  - `apps/web/src/features/tenants/api/hooks.ts` — `useMembersQuery`,
    `useInvitationsQuery`, `useTenantQuery` add an `activeTenantId`
    parameter (or read from `useMeQuery` internally) and refuse to
    run when their `tenantId` argument no longer matches the active
    tenant.
  - `apps/web/src/routes/__root.tsx` — add `errorComponent` and
    `notFoundComponent`.
  - New `apps/web/src/components/error-fallback/` slice (or under
    `components/app-shell/`): `RouteErrorCard`, `RouteNotFoundCard`,
    `RouteForbiddenCard` — Spanish copy, reuses the existing empty-card
    shape from the empresa routes.
- **Tests:** new integration files under `apps/web/tests/integration/`
  (the project keeps frontend tests mirrored to `src/`, not co-located).
- **Docs:** `docs/09-frontend.md` gains a short section on the
  query-client lifecycle rules; ADR-0001 is unaffected.
- **APIs:** none. This change does not touch `apps/api/`.
- **Out of scope (queued, not in this change):** moving the refresh
  token out of sessionStorage (requires the BFF), and the legacy-URL
  redirect map for pre-`/empresa/*` routes (covered by route guards in
  a separate hardening pass).
