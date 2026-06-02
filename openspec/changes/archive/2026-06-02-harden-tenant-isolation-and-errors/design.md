## Context

The SPA mounts a single React Query `QueryClient` per `App` instance
(see `apps/web/src/app.tsx`) and a code-based TanStack Router whose
root is `apps/web/src/routes/__root.tsx`. Per-tenant queries already
namespace under `["tenant", <id>, …]` keys
(`apps/web/src/features/tenants/api/hooks.ts:43-50`). Two safety
guarantees we expect from this design are partly missing:

- **Identity isolation:** the query client should be reset whenever
  the operator identity rotates. Tenant switching already calls
  `qc.clear()` (`useSwitchTenantMutation` at line 196 of
  `features/tenants/api/hooks.ts`). Logout does not — it only does
  `qc.removeQueries({ queryKey: meQueryKey })`
  (`features/auth/api/hooks.ts:125-135`). This is the audit's
  cross-user data-leak finding.
- **Route-level error degradation:** the audit observed a white screen
  on `/v1/me 403` and on Zod validation failures. Inspection of
  `__root.tsx` confirms there is no `errorComponent` /
  `notFoundComponent` and individual feature loaders re-throw rather
  than mapping to a fallback.

Token persistence (sessionStorage placement of the refresh token,
in-memory access/id tokens) is documented as a deliberate XSS-blast
decision in `apps/web/src/api/tokenStore.ts` and is **not** in scope
for this change.

## Goals / Non-Goals

**Goals:**

- Make logout indistinguishable from a fresh-browser identity:
  `queryClient.clear()` runs before any post-logout navigation, and
  no component can read the prior identity's cache after the mutation
  settles.
- Make tenant-switch race-safe: a per-tenant query whose `tenantId`
  argument differs from the current `me.active_tenant` MUST refuse to
  fire, regardless of whether `qc.clear()` has resolved yet.
- Make every route loader failure (403, 404, Zod parse error,
  generic `Error`) render a Spanish in-shell fallback card with a
  recovery link, never a white screen.
- The fallback for an authenticated operator on 403 routes them back
  to `/dashboard`; for an unauthenticated request (no access token) it
  routes to `/login`. A 404 always routes to `/dashboard` if
  authenticated.

**Non-Goals:**

- Reworking token storage. The post-MVP BFF + HttpOnly cookie path is
  the right place for that conversation.
- Building a global toast/error inbox. This change is route-loader
  focused; mutation errors continue to render inline in their own
  forms (covered in `harden-auth-flows` and
  `polish-empresa-ux-and-a11y`).
- Building a route-aware analytics surface for 403/404s. Telemetry
  follow-up if it surfaces in operational review.
- Adding a 410 / legacy-redirect map. The audit's "Guards" finding is
  worth addressing separately so this change stays narrow.

## Decisions

### Decision 1 — Add `qc.clear()` to logout's `onSettled`, not `onSuccess`

We considered three placements:

- `onSuccess`: only clears when logout succeeds. If the backend logout
  errors (e.g. network failure), the prior identity's cache stays in
  memory. Rejected — the operator's intent is to leave.
- `onSettled` (chosen): clears regardless of success/failure, after
  the existing `clear()` (token store) and `clearPickerConfirmed()`
  calls. Matches what tenant-switch already does and matches the
  documented intent.
- React-level effect on `me` becoming `null`: would clear on any
  identity transition (including refresh-failure on app boot), but
  introduces a re-render dependency that is harder to test. Rejected
  for now.

Ordering inside `onSettled`:

1. `clear()` from token store — invalidates the access/refresh/id
   tokens so any in-flight request that races with logout gets a 401
   instead of a fresh response keyed against the prior identity.
2. `clearPickerConfirmed()` — drops the picker session flag.
3. `qc.clear()` — drops every cache entry. Specifically called
   **after** the token store clear so any retry queued by React
   Query before this point sees the empty token store and aborts
   rather than refetching with the prior identity's bearer.

### Decision 2 — Stale-tenant guard at the query hook layer, not the component layer

Per-tenant query hooks (`useMembersQuery`, `useInvitationsQuery`,
`useTenantQuery`) currently take a `tenantId` argument and gate on
`tenantId !== ""`. We add a second gate: the hook reads
`useMeQuery().data?.active_tenant` and refuses to enable the query
when the passed `tenantId` does not match the active one. This
catches the case where a component captured the old tenant id during
the `qc.clear() → invalidateQueries(me)` window on switch.

Considered alternatives:

- Pass `activeTenantId` from every caller. Rejected — every empresa
  route would need to plumb the value, and missing a call site
  silently re-introduces the bug.
- Add a context provider that emits the active tenant. Already
  exists via `useMeQuery`; introducing a second provider would just
  duplicate it.
- Drop per-route `tenantId` arguments entirely and have the hooks
  derive the id internally. Considered — but some hooks legitimately
  need to query a different tenant (the picker, the
  `myTenants` listing). Keeping the argument while adding the guard
  is the safer middle path.

### Decision 3 — Root `errorComponent` + AppShell `errorComponent`, not a single global handler

We could put one error component on `rootRoute` and call it a day,
but the AppShell context (sidebar, header, breadcrumbs) is the
operator's mental anchor — losing it on every 403 makes the UI feel
broken even when only a child loader failed. Instead:

- `rootRoute.errorComponent` handles failures that escape the
  AppShell (router crash, root loader fails, etc.) and renders a
  bare-shell fallback that matches the `/login` chrome — no
  sidebar, no header.
- A new `AppShell` layout route (or a wrapping route group) carries
  its own `errorComponent` rendering the fallback **inside the shell**
  so the operator keeps their nav context.
- 404s go through `notFoundComponent` on `rootRoute`; if the operator
  is authenticated, the fallback renders inside the AppShell (we
  redirect into `/dashboard` and have the dashboard show a "no
  encontramos esa página" toast on arrival OR render the 404 card
  inside the shell — chosen approach: render the 404 card inside the
  shell with a `Volver al inicio` button).

### Decision 4 — Distinguish error categories by inspecting the thrown error, not by HTTP code only

The error component receives the thrown value from TanStack Router's
loader. To pick which fallback card to render we inspect:

- `ApiProblem` with `status === 403` → `RouteForbiddenCard`.
- `ApiProblem` with `status === 404` → `RouteNotFoundCard`.
- `ZodError` (from `zod`) → `RouteSchemaErrorCard` ("La respuesta del
  servidor no tiene el formato esperado.").
- Anything else → `RouteRuntimeErrorCard` (generic "Ocurrió un error
  inesperado").

The category set is intentionally small. Anything not listed falls
through to the generic card; no silent narrowing of error shapes.

### Decision 5 — Authentication-aware recovery link

The recovery link inside each fallback card needs to choose between
`/login` and `/dashboard`. We read the token store's `getAccessToken()`
synchronously inside the fallback render. If it returns `null`, the
button links to `/login`; otherwise `/dashboard`. We do not call
`useMeQuery` here because the failure that produced the boundary may
itself have been a `/me` failure, and we don't want the fallback to
trigger another request.

## Risks / Trade-offs

- **Risk:** `qc.clear()` on logout cancels in-flight requests, which
  React Query treats as an error. Components that had observers on
  those queries during logout may briefly render an error state
  before unmounting on the navigation to `/login`. → **Mitigation:**
  the logout flow already navigates synchronously after `onSettled`;
  acceptable transient state. Verified in integration test.
- **Risk:** Adding an `active_tenant` gate to per-tenant queries
  changes hook semantics for any caller currently passing a custom
  tenant id (e.g. an admin tool). → **Mitigation:** today the only
  callers are the empresa routes (the picker uses `myTenantsKey`,
  which is not affected). If a future caller needs to query a
  non-active tenant, add an opt-out via a parameter; we don't
  pre-build that.
- **Risk:** Error fallbacks that themselves throw produce the same
  white screen we are trying to avoid. → **Mitigation:** the fallback
  components are pure functions over the error value; they do not
  fetch, do not call hooks that can suspend, and do not depend on
  `useMeQuery`. Covered by a unit test that renders each fallback
  with each error category.
- **Trade-off:** rendering the 404 card inside the AppShell when the
  URL is genuinely garbage (`/foobar`) implies the operator was
  "trying to go somewhere in the app" — which is the common case but
  not universal (a stale email link could land them there). The
  alternative (404 outside the shell) felt more disorienting in
  hands-on. Revisit if telemetry shows the 404 path is being
  triggered by external referrers.

## Migration Plan

Single deploy. No data migration. Tests run against the new
fallback components and the updated hooks before merging. No
feature-flag scaffolding — these are correctness fixes.

## Open Questions

- Should the `RouteForbiddenCard` offer a "Solicitar acceso" link to
  the empresa owner (mailto + tenant-owner lookup) in addition to
  the recovery button? Defer to product. Current change ships
  without it.
- Should `qc.clear()` also run on app boot when the bootstrap
  refresh-token exchange fails? Probably yes — but the failure path
  in `app.tsx`'s boot effect currently navigates to `/login`
  immediately, which unmounts the QueryClient consumers. Leaving as
  follow-up.
