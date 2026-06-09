# frontend-shell Specification

## Purpose
TBD - created by archiving change add-frontend-walking-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Vite entry HTML loads the React bundle

The frontend SHALL ship an `apps/web/index.html` that Vite serves as the application entry. The entry MUST declare UTF-8 encoding, a responsive viewport meta tag, a document title of `nica-erp`, and a single root mount point with `id="root"`. The HTML MUST load `/src/main.tsx` as an ES module and MUST NOT hard-code colour utility classes on the `<body>` element (presentation comes from the Tailwind base layer).

#### Scenario: Vite serves the entry HTML

- **WHEN** `pnpm dev` is running and an HTTP GET is issued to `http://localhost:5173/`
- **THEN** the server responds `200 OK` with HTML containing `<div id="root"></div>`, `<title>nica-erp</title>`, and a `<script type="module" src="/src/main.tsx">` reference

#### Scenario: Entry HTML defers presentation to the base layer

- **WHEN** the project is inspected at `apps/web/index.html`
- **THEN** the `<body>` element carries no Tailwind utility classes (background and foreground colour come from the `body { @apply bg-background text-foreground ... }` rule in `src/styles/globals.css`)

### Requirement: React root is rendered under StrictMode with a single App component

`apps/web/src/main.tsx` SHALL locate the `#root` element, throw a descriptive error if it is missing, and mount `<App />` inside `<StrictMode>` via `createRoot`. It MUST import `@/styles/globals.css` at module top level so the stylesheet is bundled with the entry chunk.

#### Scenario: Root element missing aborts boot

- **WHEN** `apps/web/index.html` is loaded but the `#root` element has been removed
- **THEN** `main.tsx` throws an Error with message `"Missing #root element"` rather than silently failing

#### Scenario: StrictMode wraps the application

- **WHEN** `main.tsx` is read
- **THEN** the rendered tree is `<StrictMode><App /></StrictMode>` and `@/styles/globals.css` is imported at module scope

### Requirement: App component provides the TanStack Query client

`apps/web/src/app.tsx` SHALL export a single React component `App` that constructs a `QueryClient` exactly once per component instance (via `useState` initializer) and wraps the application tree in `<QueryClientProvider>`. The provider MUST wrap the sprint-00 `IndexRoute`. The router is not mounted in sprint 00; routing arrives in a later sprint.

#### Scenario: QueryClient is created lazily and stably

- **WHEN** `App` mounts
- **THEN** `new QueryClient()` runs once via `useState(() => new QueryClient())` so the client survives re-renders without reinstantiation

#### Scenario: IndexRoute renders inside the query provider

- **WHEN** `App` is rendered into a happy-dom tree under test
- **THEN** the rendered output contains the `IndexRoute` markup nested inside a `QueryClientProvider`

### Requirement: Path alias `@/` resolves to `apps/web/src`

Both Vite and TypeScript SHALL resolve the import specifier `@/*` to `apps/web/src/*`. Source code MUST consume sibling modules through this alias (e.g. `import { IndexRoute } from "@/routes/index"`) rather than long relative paths, so files can move without churning imports.

#### Scenario: Vite resolves the alias at runtime

- **WHEN** any module imports `@/styles/globals.css` or `@/app`
- **THEN** Vite resolves the specifier to `apps/web/src/styles/globals.css` / `apps/web/src/app.tsx` via `resolve.alias` in `vite.config.ts`

#### Scenario: TypeScript resolves the alias at compile time

- **WHEN** `pnpm typecheck` runs
- **THEN** `tsc` resolves `@/*` to `./src/*` via `compilerOptions.paths` in `apps/web/tsconfig.json` and reports no `cannot find module '@/...'` errors

### Requirement: Sidebar supports multi-level entries

`apps/web/src/components/app-sidebar/sidebar.tsx` SHALL export two
new primitives:

- `<SidebarMenuSub>` — a `<ul>` rendered as the parent item's
  child container. It accepts a `defaultOpen?: boolean` prop and
  toggles open/closed state.
- `<SidebarMenuSubButton>` — a child row that renders a link
  styled with a leading icon slot, label, and a left-rule
  indicator showing the active state.

The parent row that owns a `<SidebarMenuSub>` MUST render a
chevron (`ChevronRight` rotating to `ChevronDown` when open)
between the label and the row's right edge. Clicking anywhere on
the parent row toggles the section; clicking specifically on a
nested item navigates without collapsing the section.

The open/closed state of each multi-level section MUST persist
under
`localStorage["nica-erp:sidebar-<section>-open"]`
(e.g. `nica-erp:sidebar-empresa-open` for the `Empresa` section)
so the operator's preference survives reloads.

In the collapsed sidebar variant (the desktop chip-only mode),
the parent row MUST render as an icon-only button; clicking it
opens a Tooltip-anchored popover listing the nested items.

#### Scenario: Empresa section expands and persists its state

- **GIVEN** the operator clicks the `Empresa` parent row in the
  sidebar (initial state: collapsed)
- **WHEN** the section expands and the operator reloads the page
- **THEN** `localStorage["nica-erp:sidebar-empresa-open"]` is
  `"1"` and the section renders expanded on first paint

#### Scenario: Clicking a sub-item navigates without collapsing

- **GIVEN** the `Empresa` section is expanded
- **WHEN** the operator clicks the `Usuarios` sub-item
- **THEN** the SPA navigates to `/empresa/usuarios` and the
  section stays expanded

### Requirement: Sidebar nav uses the `Empresa` multi-level entry

`apps/web/src/components/app-sidebar/app-sidebar.tsx` SHALL render
the navigation as:

1. `Resumen` → `/dashboard`
2. `Ventas` → `/sales`
3. `Inventario` → `/inventory`
4. `Reportes` → `/reports`
5. `Empresa` (parent, icon `Building2`) — `<SidebarMenuSub>` with
   children:
   - `Vista general` → `/empresa`
   - `Usuarios` → `/empresa/usuarios`
   - `Configuración` → `/empresa/configuracion`
6. `Settings` → `/settings`

The previous flat `Tenants` → `/tenants` entry SHALL be removed.
The picker is reachable from the `TenantSwitcher`'s `Cambiar
empresa` row introduced by [[force-tenant-picker-and-back-link]].

#### Scenario: Sidebar no longer exposes a flat `Tenants` link

- **WHEN** the AppShell renders for any authenticated route
- **THEN** the sidebar's nav lists `Resumen`, `Ventas`,
  `Inventario`, `Reportes`, `Empresa`, `Settings` — no `Tenants`
  entry

#### Scenario: Empresa parent matches the active sub-route

- **GIVEN** the operator is on `/empresa/usuarios`
- **WHEN** the sidebar renders
- **THEN** the `Empresa` parent row is marked as active (rendered
  with the active-state styling) and the `Usuarios` child row is
  also marked as active

### Requirement: `nav-user` exposes a `Mi cuenta` entry

`apps/web/src/components/app-sidebar/nav-user.tsx` SHALL render a
`Mi cuenta` entry in the user menu (the popover that opens from
the operator's avatar in the sidebar footer). Activating the entry
SHALL navigate to `/account`.

The entry MUST be present even on collapsed sidebars (it shows up
in the user menu's popover regardless of sidebar state).

#### Scenario: User menu lists Mi cuenta

- **WHEN** the operator opens the user menu in the sidebar footer
- **THEN** the menu lists `Mi cuenta` and `Cerrar sesión`

### Requirement: `/account` renders outside the AppShell

The route `/account` SHALL render with a lightweight
`<IdentityLayout>` chrome instead of `<AppShell>`. The layout
SHALL contain:

- A top bar with the sidebar's `TenantSwitcher` chip on the right
  (so the operator can still switch empresas without crossing
  back through `/tenants`).
- A `← Volver` link on the left that navigates back to the last
  AppShell route the operator visited
  (`sessionStorage["nica-erp:last-app-route"]`, defaulting to
  `/dashboard`).
- No sidebar.

`<AppShell>` SHALL update its route mount effect to write the
current pathname to
`sessionStorage["nica-erp:last-app-route"]` so the back link has
a target.

The three identity cards on the page (Profile, Empresa activa,
Permisos) stay structurally identical.

#### Scenario: /account does not render the sidebar

- **WHEN** the operator navigates to `/account`
- **THEN** the rendered DOM contains no `[data-sidebar]` element
  and no `<SiteHeader>` element

#### Scenario: Volver returns to the last AppShell route

- **GIVEN** the operator was on `/empresa/usuarios` and navigated
  to `/account`
- **WHEN** the operator clicks `← Volver`
- **THEN** the SPA navigates to `/empresa/usuarios`

#### Scenario: Volver defaults to /dashboard for first-time visitors

- **GIVEN** `sessionStorage["nica-erp:last-app-route"]` is unset
  (operator navigated directly to `/account` from a deep link)
- **WHEN** the operator clicks `← Volver`
- **THEN** the SPA navigates to `/dashboard`

### Requirement: `/tenants/$id/members` is removed

The flat route `apps/web/src/routes/tenants/members.tsx` SHALL be
deleted. The router config SHALL drop the corresponding route
registration.

Any in-app link that pointed at `/tenants/$id/members` MUST be
updated to `/empresa/usuarios` (the link no longer carries the
`$id`; clicking it assumes the active empresa is the one the
operator wants to manage).

#### Scenario: Old members deep link redirects to the empresa group

- **WHEN** the SPA receives a navigation to `/tenants/<uuid>/members`
- **THEN** the router does not find a registered route and the
  router's fallback redirects to `/empresa/usuarios`

### Requirement: Tenants flat router section keeps the picker + create routes

The SPA SHALL keep `/tenants` (picker) and `/tenants/new` (create
wizard) registered as routes that render outside the AppShell —
the layout decision matches [[force-tenant-picker-and-back-link]].
Both routes SHALL stay reachable from:

- The `TenantSwitcher`'s `Cambiar empresa` row.
- The empty-state link from `/empresa` when the operator has no
  active empresa.
- Direct URL entry.

#### Scenario: Picker route stays reachable from the switcher

- **GIVEN** the operator is on `/dashboard`
- **WHEN** the operator opens the sidebar's `TenantSwitcher` and
  clicks `Cambiar empresa`
- **THEN** the SPA navigates to `/tenants` (the picker) without
  rendering the AppShell

