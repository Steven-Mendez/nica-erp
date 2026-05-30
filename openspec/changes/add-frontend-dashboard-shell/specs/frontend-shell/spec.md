## ADDED Requirements

### Requirement: `AppShell` composes sidebar + site header + main column

`apps/web/src/components/app-shell/AppShell.tsx` SHALL export a
single React component `AppShell` that renders, in order:

1. `<SidebarProvider>` from `components/app-sidebar/sidebar-context`,
   wrapping
2. `<AppSidebar />` from `components/app-sidebar/app-sidebar`,
3. a `<main>` element occupying the remaining viewport width that
   itself renders `<SiteHeader />` followed by `{children}`.

Authenticated routes SHALL opt into the shell by returning
`<AppShell>{...page content}</AppShell>`. Auth screens
(`/login`, `/signup`, `/confirm`, `/forgot-password`,
`/reset-password`) and the public `/invitations/$token/accept`
route SHALL NOT render the shell.

#### Scenario: Authenticated route renders the shell

- **GIVEN** the user has an access token and navigates to
  `/dashboard`
- **WHEN** the route renders
- **THEN** the DOM SHALL contain exactly one `<AppSidebar>`,
  exactly one `<SiteHeader>`, and the route's page content as the
  main column's last child

#### Scenario: Login route bypasses the shell

- **GIVEN** the user navigates to `/login`
- **WHEN** the route renders
- **THEN** the DOM SHALL NOT contain any `data-sidebar` element

### Requirement: Sidebar state persists to `localStorage`

`SidebarProvider` SHALL expose `state: "expanded" | "collapsed"`
and a `toggle()` method. On mount, the provider SHALL read
`localStorage["nica-erp:sidebar-state"]` and use its value if it
matches one of the two literals; otherwise the initial state SHALL
be `"expanded"`. On every change, the provider SHALL write the
new value back to the same key.

Mobile open/close state (the off-canvas drawer) SHALL live in a
separate `useState` inside the provider and SHALL NOT touch
`localStorage`. The drawer SHALL initialise to `closed` on every
mount.

#### Scenario: Collapse toggle persists across reload

- **GIVEN** the sidebar is `expanded` and the user clicks the
  trigger to collapse it
- **WHEN** the page reloads
- **THEN** `useSidebar()` SHALL report `state === "collapsed"` on
  first render

#### Scenario: Mobile drawer does not persist

- **GIVEN** the mobile drawer is `open`
- **WHEN** the page reloads
- **THEN** the drawer SHALL initialise to `closed`

### Requirement: `AppSidebar` exposes the navigation surface

`apps/web/src/components/app-sidebar/app-sidebar.tsx` SHALL render:

- A `<SidebarHeader>` hosting `<TenantSwitcher>`. When the user has
  zero memberships, the header SHALL render `"No active tenant"`
  with a `<Link to="/tenants/new">`.
- A `<SidebarContent>` containing one `<SidebarGroup>` with six
  `<SidebarMenuItem>` entries in this order:
  `Overview /dashboard`, `Sales /sales`, `Inventory /inventory`,
  `Reports /reports`, `Tenants /tenants`,
  `Settings /settings`. Each item SHALL render a `lucide-react`
  icon to the left of the label.
- A `<SidebarFooter>` with a `<Link to="/account">` and a
  `<Button>` that invokes `useLogoutMutation().mutate()`.

Active item highlighting SHALL be derived from
`router.state.location.pathname` starting with the item's path
(e.g. `/tenants/new` highlights `Tenants`).

Permission gating per nav item is **out of scope** for this change
(sprint 04+ wraps each item in `<Can>` as the real screen ships).

#### Scenario: Sign-out from the footer

- **WHEN** the user clicks the `Sign out` button in the sidebar
  footer
- **THEN** `useLogoutMutation().mutate()` SHALL be invoked

### Requirement: `TenantSwitcher` lives in the sidebar header

`apps/web/src/components/app-sidebar/tenant-switcher.tsx` SHALL
contain the `TenantSwitcher` previously located in
`components/topbar/`. Its public contract SHALL match the contract
specified by the sprint-03 frontend-shell capability:

- Calls `POST /v1/tenants/{tenantId}/switch` with the in-memory
  `refresh_token` in the body.
- On success, calls `tokenStore.setTokens(...)`, then
  `queryClient.clear()`, then `router.invalidate()`.
- On failure, surfaces an error UI and leaves the previous tenant
  active.

The previous `apps/web/src/components/topbar/` directory SHALL be
removed.

#### Scenario: Switcher still clears caches on success

- **WHEN** `TenantSwitcher.onChange(<T>)` resolves successfully
- **THEN** `tokenStore.getAccessToken()` SHALL return the new
  access token, `queryClient.clear()` SHALL have been called
  exactly once, and `router.invalidate()` SHALL have been called
  exactly once

### Requirement: `/dashboard` ships placeholder KPI/chart/table shapes

`apps/web/src/routes/dashboard.tsx` SHALL render `<AppShell>`
wrapping:

- Four `<Card>` slots in a 2-column grid (single column on
  `< md`); each card SHALL contain a `<CardHeader>` with title
  `"Placeholder KPI N"` (N = 1..4) and a `<CardContent>` rendering
  a `<Skeleton className="h-6 w-24">`.
- One chart-shaped `<Card>` with a `<Skeleton className="h-64">`
  and a label `"Trend chart placeholder"`.
- One table-shaped `<Card>` with a labelled
  `<Skeleton className="h-48">` and a label
  `"Recent activity placeholder"`.

The route SHALL NOT call any backend endpoint.

#### Scenario: Dashboard makes no network requests

- **GIVEN** the user lands on `/dashboard`
- **WHEN** the route renders
- **THEN** no `fetch` SHALL be issued on first paint (verified by
  vitest with a `fetch` spy)

### Requirement: Section placeholders advertise that the section is coming

Each of `apps/web/src/routes/{sales,inventory,reports,settings}.tsx`
SHALL render `<AppShell>` wrapping a single `<Card>` with:

- `<CardTitle>` matching the nav label (`Sales`, `Inventory`,
  `Reports`, `Settings`).
- `<CardDescription>` containing the literal string
  `Coming soon.`
- A `<CardContent>` body with a one-line hint of what will land
  there (no sprint numbers, no dates).

Routes SHALL NOT call any backend endpoint and SHALL NOT render
fake data. Product UI SHALL NOT reference internal sprint numbers.

#### Scenario: Sales placeholder advertises the coming section

- **GIVEN** the user navigates to `/sales`
- **WHEN** the route renders
- **THEN** the `CardDescription` SHALL contain the substring
  `Coming soon` and SHALL NOT contain the substring `sprint`

### Requirement: `/account` renders profile, tenant, and permission cards

`apps/web/src/routes/account.tsx` SHALL render `<AppShell>`
wrapping three cards:

1. **Profile card** — title `Profile`; fields rendered as a
   description list: `id` (mono font), `email`, `display_name`
   (or `—` when null), `locale` (or `—`), `timezone` (or `—`).
2. **Active tenant card** — title `Active tenant`; renders the
   active tenant's `name` and `ruc` plus a `<Badge>` showing the
   role. When `me.active_tenant === null`, the card body renders
   `No active tenant` with a `<Link to="/tenants/new">`.
3. **Permissions card** — title `Permissions`; renders
   `me.permissions` as a bulleted list. When the list is empty,
   the body renders `No permissions`.

Data sources: `useMeQuery()` for fields 1 and 3 + the
active-tenant id; `useMyTenantsQuery()` filtered by
`me.active_tenant` for the tenant card's name + RUC. No additional
endpoints SHALL be queried.

#### Scenario: Account card renders three sections

- **GIVEN** `useMeQuery` resolves with `{id, email, role,
  permissions: ["tenant:read","members:read"]}` and
  `useMyTenantsQuery` resolves with one membership whose
  `tenant_id === me.active_tenant`
- **WHEN** `/account` renders
- **THEN** the DOM SHALL contain exactly three `<Card>` elements
  whose titles are `Profile`, `Active tenant`, `Permissions` in
  that order

#### Scenario: Account without active tenant

- **GIVEN** `useMeQuery` resolves with `active_tenant: null,
  role: null, permissions: []`
- **WHEN** `/account` renders
- **THEN** the tenant card body SHALL contain the substring
  `No active tenant` and the permissions card body SHALL contain
  `No permissions`

### Requirement: `/me` redirects to `/account`

`apps/web/src/routes/me.tsx` SHALL register a `beforeLoad` that
throws `redirect({ to: "/account" })`. Direct navigation to `/me`
SHALL never render the old `/me` component; the router SHALL land
the user on `/account`.

#### Scenario: Direct navigation to `/me` lands on `/account`

- **GIVEN** the user enters `/me` in the address bar with a valid
  access token
- **WHEN** the router resolves the navigation
- **THEN** `router.state.location.pathname` SHALL be `/account`

### Requirement: Index route redirects based on auth state

`apps/web/src/router.ts`'s `indexRoute` (`path: "/"`) `beforeLoad`
SHALL inspect `tokenStore.getAccessToken()`:

- When the token is non-null, throw `redirect({ to: "/dashboard" })`.
- Otherwise, throw `redirect({ to: "/login" })`.

#### Scenario: Logged-in user lands on /dashboard

- **GIVEN** an access token is in `tokenStore`
- **WHEN** the user navigates to `/`
- **THEN** the router resolves to `/dashboard`

#### Scenario: Anonymous visitor lands on /login

- **GIVEN** no access token is in `tokenStore`
- **WHEN** the user navigates to `/`
- **THEN** the router resolves to `/login`

### Requirement: Post-login navigation lands on /dashboard

`useLoginMutation`'s `onSuccess` and
`useCreateTenantMutation`'s `onSuccess` handlers SHALL navigate to
`/dashboard` instead of `/me`. Existing token-persistence and
cache-invalidation behaviour is unchanged.

#### Scenario: Login success navigates to /dashboard

- **GIVEN** the user submits valid credentials at `/login`
- **WHEN** the login mutation resolves
- **THEN** `router.state.location.pathname` SHALL become
  `/dashboard`
