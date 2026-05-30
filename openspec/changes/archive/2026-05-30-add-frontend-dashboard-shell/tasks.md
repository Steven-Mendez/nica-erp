## 1. Sidebar primitives (`components/app-sidebar/`)

- [x] 1.1 Create `components/app-sidebar/sidebar-context.tsx`:
      `SidebarProvider` (state: `expanded` | `collapsed` + mobile
      `open` | `closed`), `useSidebar()` hook, `localStorage`
      hydration under key `nica-erp:sidebar-state`.
- [x] 1.2 Create `components/app-sidebar/sidebar.tsx` with
      `Sidebar`, `SidebarHeader`, `SidebarContent`,
      `SidebarFooter`, `SidebarGroup`, `SidebarGroupLabel`,
      `SidebarMenu`, `SidebarMenuItem`, `SidebarMenuButton`,
      `SidebarSeparator`. Use `data-state` and Tailwind utilities;
      no radix dependencies.
- [x] 1.3 Create `components/app-sidebar/app-sidebar.tsx` (the
      project-specific composition): header hosts
      `TenantSwitcher`; content hosts a single `SidebarGroup` with
      the six nav items (`Overview /dashboard`, `Sales /sales`,
      `Inventory /inventory`, `Reports /reports`,
      `Tenants /tenants`, `Settings /settings`); footer hosts
      `Account` link + `Sign out` button.

## 2. App shell (`components/app-shell/`)

- [x] 2.1 Create `components/app-shell/site-header.tsx`: sidebar
      trigger button (icon `Menu`), breadcrumb derived from
      `router.state.matches`, theme toggle (reuse existing
      `<ThemeToggle>` from sprint 02).
- [x] 2.2 Create `components/app-shell/app-shell.tsx`: wraps
      `SidebarProvider`, renders `<AppSidebar/>` + main column with
      `<SiteHeader/>` then `{children}`.
- [x] 2.3 Vitest: `app-shell.test.tsx` renders `AppShell` under a
      `MemoryRouter`, asserts sidebar + header are present, asserts
      `children` mount in the main column.

## 3. TenantSwitcher relocation

- [x] 3.1 Move `TenantSwitcher` from
      `components/topbar/TenantSwitcher.tsx` to
      `components/app-sidebar/tenant-switcher.tsx`. Re-style as a
      sidebar header block (active tenant name + role on the first
      line, dropdown icon, member list expands below). Public
      contract unchanged.
- [x] 3.2 Update sidebar header in `app-sidebar.tsx` to host
      `TenantSwitcher`. When the user has zero memberships, the
      header collapses to a `"No active tenant"` placeholder + a
      link to `/tenants/new`.
- [x] 3.3 Delete `components/topbar/Topbar.tsx` and
      `components/topbar/TenantSwitcher.tsx`. Remove the
      `components/topbar/` directory.
- [x] 3.4 Update existing vitest tests that imported
      `Topbar` / `TenantSwitcher` from `components/topbar/` to
      import from the new path.

## 4. New routes

- [x] 4.1 `routes/dashboard.tsx` — `<AppShell>` + four KPI card
      slots in a 2×2 grid (`<Card>` with `Skeleton` body), one
      chart-shaped panel, one table-shaped panel. No backend calls.
- [x] 4.2 `routes/sales.tsx`, `routes/inventory.tsx`,
      `routes/reports.tsx`, `routes/settings.tsx` — each renders
      `<AppShell>` + a single `<Card>` titled with the nav label
      and a "Coming soon." description (no sprint numbers in
      product UI).
- [x] 4.3 `routes/account.tsx` — `<AppShell>` + three cards:
      Profile (id, email, display_name, locale, timezone), Active
      tenant (name + RUC + role badge), Permissions (list).
      `useMeQuery()` + filter `useMyTenantsQuery().items` by
      `me.active_tenant`.

## 5. Routing wiring

- [x] 5.1 In `router.ts`: register `dashboardRoute`, `salesRoute`,
      `inventoryRoute`, `reportsRoute`, `settingsRoute`,
      `accountRoute`. Lazy-load each via
      `lazyRouteComponent`. Add to the `addChildren([...])` array.
- [x] 5.2 Replace `indexRoute`'s `beforeLoad` to check
      `tokenStore.getAccessToken()` and redirect to `/dashboard`
      when present, `/login` when absent.
- [x] 5.3 Replace `meRoute`'s component with a `beforeLoad` that
      throws `redirect({ to: "/account" })`. The `routes/me.tsx`
      file is updated to export a no-op component (the redirect
      happens before render).

## 6. Auth + tenant create redirect targets

- [x] 6.1 In `features/auth/api/hooks.ts`: `useLoginMutation`'s
      `onSuccess` calls `router.navigate({ to: "/dashboard" })`
      instead of `/me`.
- [x] 6.2 In `features/tenants/api/hooks.ts`:
      `useCreateTenantMutation`'s success handler navigates to
      `/dashboard` instead of `/me` / `/tenants/$id`.

## 7. Existing route updates

- [x] 7.1 Wrap `/tenants`, `/tenants/new`, `/tenants/$id/members`
      in `<AppShell>` so the sidebar is present on those pages.
      Keep their content unchanged.

## 8. Tests

- [x] 8.1 `dashboard.test.tsx`: renders without `useQuery` errors,
      asserts the four KPI slots + chart slot + table slot are
      present (count + skeleton presence).
- [x] 8.2 `account.test.tsx`: with a mocked `useMeQuery` resolving
      to a fixture, asserts the three cards render with the
      fixture's values (id, email, role, permission count).
- [x] 8.3 `sidebar.test.tsx`: collapse toggle flips the
      `data-state` attribute and persists to `localStorage`; mobile
      open/close does not touch `localStorage`. (Implemented as
      `tests/unit/components/app-sidebar/sidebar-context.test.tsx`
      verifying the context-level invariants the DOM mirrors.)
- [x] 8.4 Update `tenants.test.tsx` / `me.test.tsx` if they
      asserted DOM from the old topbar. [no-op: neither file exists in the current test layout — the dashboard-shell migration predates the route names involved here]

## 9. Documentation cross-checks

- [x] 9.1 `docs/sprints/03-tenants-and-rls.md` already references
      the new section; verify the link anchor resolves.
- [x] 9.2 `docs/09-frontend.md` already references the shell;
      verify the structure tree matches the implemented
      directories.
- [x] 9.3 No new ADR. The shell is a code organisation choice that
      sits inside [ADR-0009 — frontend stack]
      (../../../docs/adr/0009-frontend-stack.md); no architectural
      decision to record.

## 10. Verification

- [x] 10.1 `pnpm --filter @nica-erp/web typecheck` exit 0.
- [x] 10.2 `pnpm --filter @nica-erp/web lint` exit 0 (including
      the cross-feature import rule).
- [x] 10.3 `pnpm --filter @nica-erp/web test --run` exit 0.
- [x] 10.4 `pnpm --filter @nica-erp/web build` exit 0.
- [ ] 10.5 Manual: `pnpm dev`, log in, land on `/dashboard`, open
      sidebar in collapsed + expanded mode, navigate to
      `/account`, verify `/v1/me` data renders, log out, verify
      redirect to `/login`.
