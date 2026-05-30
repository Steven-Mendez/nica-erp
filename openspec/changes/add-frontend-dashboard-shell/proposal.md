## Why

Sprint 03 closes with `features/tenants/` slice and a thin `Topbar` that
hosts the `TenantSwitcher` and a sign-out button. That topbar is
adequate for the four tenant routes plus `/me`, but sprints 04-08 add
five new bounded-context surfaces (catalog, inventory, parties, sales,
taxes/payments/reports) that share a single SPA. Without an app shell
each sprint has to re-invent navigation, breadcrumbing, and the sign-out
affordance — and the user has no consistent landing page after login.

This change introduces the **app shell** that every authenticated route
will live inside from this sprint onwards, modeled on the shadcn
[`dashboard-01`](https://ui.shadcn.com/blocks) block (sidebar + site
header). The shell is placeholder-only for the not-yet-built sections:
sprints 04-08 fill the placeholders without touching the shell. The
exception is `/account`, a real screen sourced from the existing
`GET /v1/me` that supersedes sprint 02's `/me` page.

Reference:
[`docs/sprints/03-tenants-and-rls.md` §Dashboard shell + account screen](../../../docs/sprints/03-tenants-and-rls.md#dashboard-shell--account-screen),
[`docs/09-frontend.md` §App shell](../../../docs/09-frontend.md#app-shell).

## What Changes

### Frontend — app shell primitives

- New `apps/web/src/components/app-sidebar/` directory with the
  primitives `Sidebar`, `SidebarHeader`, `SidebarContent`,
  `SidebarFooter`, `SidebarGroup`, `SidebarGroupLabel`,
  `SidebarMenu`, `SidebarMenuItem`, `SidebarMenuButton`,
  `SidebarSeparator`, and the project-specific `AppSidebar` that
  wires the nav (`Overview`, `Sales`, `Inventory`, `Reports`,
  `Tenants`, `Settings`) plus a footer (`Account` link +
  `Sign out` button). The header hosts the `TenantSwitcher`.
- The sidebar collapses to icon-only when the user toggles via the
  site-header trigger; state lives in a `SidebarProvider` context
  persisted to `localStorage` under key `nica-erp:sidebar-state`.
  Mobile (`< md`) hides the rail entirely and reveals it as an
  overlay when the trigger is pressed.
- New `apps/web/src/components/app-shell/` directory with
  `AppShell.tsx` (composes `SidebarProvider` + `AppSidebar` + main
  column) and `SiteHeader.tsx` (sidebar trigger, breadcrumb derived
  from `useMatches()`, theme toggle). No page actions live in
  `SiteHeader`; each route owns its own primary actions.
- No new npm dependencies. The sidebar tokens
  (`--sidebar`, `--sidebar-foreground`, `--sidebar-primary`,
  `--sidebar-accent`, `--sidebar-border`, `--sidebar-ring`) already
  live in `apps/web/src/styles/globals.css` from the sprint-02
  theme.

### Frontend — TenantSwitcher relocation

- `TenantSwitcher` moves from `components/topbar/Topbar.tsx` into
  `components/app-sidebar/AppSidebar.tsx`. Its public contract is
  unchanged: it still calls `POST /v1/tenants/{id}/switch`, persists
  the returned tokens, calls `queryClient.clear()` and
  `router.invalidate()`. Internal layout changes (it now renders as
  a sidebar header instead of a topbar fragment).
- `components/topbar/Topbar.tsx` is removed. Its sign-out
  responsibility moves to the sidebar footer.

### Frontend — routes

- New routes registered in `apps/web/src/router.ts`:
  - `/dashboard` — placeholder with four KPI-shaped `<Card>` slots
    plus a chart-shaped panel and a table-shaped panel. **No
    backend calls.**
  - `/sales`, `/inventory`, `/reports`, `/settings` — each renders
    a single `<Card>` with title matching the nav label and a
    one-line "Coming soon" description (no sprint numbers in UI).
  - `/account` — **real screen.** Reads `GET /v1/me` and renders
    three cards: profile, active tenant, permissions.
- `/me` becomes a permanent redirect to `/account` (via
  `beforeLoad: () => throw redirect({ to: "/account" })`). The
  existing `apps/web/src/routes/me.tsx` file is replaced by a
  thin re-export that mounts `/account`'s component so any
  remaining link to `/me` still works on direct navigation.
- `/` (the root index route) redirects to `/dashboard` when an
  access token is present in `tokenStore`, otherwise to `/login`.
  This supersedes the sprint-02 unconditional redirect to `/login`.
- Login success and successful tenant creation both navigate to
  `/dashboard` instead of `/me`.

### Frontend — placeholder rules (enforced by review)

- A placeholder route MUST NOT call the backend. `useQuery` against
  a non-existent endpoint would produce 404 noise in the error
  mapper and burn render cycles.
- A placeholder route MUST render exactly one `<Card>` with the
  nav label as title and a one-line "Coming soon." description.
  Product UI MUST NOT mention internal sprint numbers.
- The `dashboard` placeholder is the exception: it ships KPI /
  chart / table **shape** scaffolding so sprints 04-08 can drop
  real components in known anchors. The scaffolding renders empty
  skeletons (no fake data).

### Frontend — auth flow updates

- `useLoginMutation`'s `onSuccess` redirect target switches from
  `/me` to `/dashboard`.
- `useCreateTenantMutation`'s `onSuccess` redirect target switches
  from `/me` to `/dashboard`.
- The auth-aware fallback inside `/account` (the "Not signed in"
  card) follows the existing `/me` pattern — link to `/login` via
  `AuthLayout`.

## Capabilities

### Modified Capabilities

- `frontend-shell` — adds the `AppShell` + `AppSidebar` primitives,
  the placeholder routes, the `/account` page, the `/me → /account`
  redirect, the `/ → /dashboard` redirect, and the relocation of
  `TenantSwitcher` from the topbar to the sidebar header. The
  cross-feature import rule, the `useHasPermission` hook, and the
  tenant-namespaced query keys established by sprint 03 are
  **unchanged**.

## Impact

- **Affected code**: new `apps/web/src/components/app-shell/`, new
  `apps/web/src/components/app-sidebar/`, new
  `apps/web/src/routes/{dashboard,sales,inventory,reports,settings,account}.tsx`,
  modifications to `apps/web/src/router.ts`,
  `apps/web/src/routes/me.tsx` (replaced by redirect),
  `apps/web/src/features/auth/api/hooks.ts` (login redirect target),
  `apps/web/src/features/tenants/api/hooks.ts` (create-tenant
  redirect target). Removal of `apps/web/src/components/topbar/`.
- **Affected APIs**: none. The shell consumes existing endpoints
  only (`GET /v1/me`, `GET /v1/tenants/me`, `POST /v1/tenants/{id}/switch`).
- **Dependencies**: no new npm packages. Built on Tailwind utility
  classes and the existing sidebar CSS tokens.
- **Backend**: untouched. No migration, no settings, no router
  changes.
- **Tests**: Vitest gains coverage for the sidebar open/collapse
  state, `AppShell` rendering, the `/dashboard` placeholder
  structure, and the `/account` render-from-mock case. Existing
  sprint-03 frontend tests for `TenantSwitcher` and tenant routes
  stay green after the topbar→sidebar relocation.
- **Out of scope** (intentionally):
  - Real KPI / chart / table content on `/dashboard` (each lands
    with its bounded context in sprints 04-08).
  - Sidebar permission gating per nav item (deferred to sprint 04
    when the first real screen ships and a hidden vs. empty
    distinction becomes observable).
  - Mobile drawer animation polish (the rail simply shows/hides on
    small screens for MVP).
  - Settings screen content — only the placeholder. Real
    operator settings (theme, language, defaults) ship as part of
    sprint 08.
  - Tests for the `/me → /account` redirect path beyond a single
    smoke case.
