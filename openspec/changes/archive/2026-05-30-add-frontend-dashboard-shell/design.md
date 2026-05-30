# Design — Frontend dashboard shell

## Context

Sprint 03 lands the `tenants/` bounded context, four tenant routes,
and a thin `Topbar` that hosts the `TenantSwitcher`. From sprint 04
onwards five more bounded contexts each grow a frontend surface
inside the same SPA. We need a single navigation chrome those
sprints reuse unchanged.

Reference for the look-and-feel: shadcn's `dashboard-01` block
(sidebar header with switcher → nav groups → footer with user
controls; site-header on top of the main column carrying breadcrumb
and trigger; main column hosts the route's `<Outlet/>`).

## Decisions

### D1 — No new npm dependencies

The shadcn `dashboard-01` block depends on a non-trivial stack:
`@radix-ui/react-dialog` (Sheet), `@radix-ui/react-dropdown-menu`
(user menu), `@radix-ui/react-tooltip` (icon-only sidebar),
`@radix-ui/react-separator`, `@radix-ui/react-avatar`,
`@radix-ui/react-slot`, plus recharts for the chart and TanStack
Table for the table.

We **don't install any of them in this change**. Reasons:

- The chart and table are placeholders. Pulling recharts and
  TanStack Table for empty skeletons inflates the bundle and locks
  us into versions before we know what each bounded context
  actually needs in sprints 04-08.
- The sidebar collapse + mobile drawer can be implemented with CSS
  + `data-state` attributes and a tiny React context (~30 lines).
  Sheet/Dialog only buy us the focus-trap and ESC-to-close, which
  matter less for a sidebar than for a true modal — and the
  mobile drawer in this sprint is the bare-minimum show/hide.
- The user menu in `dashboard-01`'s footer (Account / Billing /
  Notifications / Sign out) collapses for us to two items
  (Account, Sign out). A native `<Link>` + `<Button>` pair in the
  sidebar footer is clearer than a dropdown for two items.

When sprint 04 ships the first real screen, the bounded context
that needs Dialog/Dropdown will pull the radix package directly.
Until then the shell stays dependency-free.

### D2 — `AppShell` is per-route, not router-level

Two ways to compose the shell:

- **(A) router-level**: the root route renders `<AppShell><Outlet/></AppShell>`,
  and an `id` route segment opts auth screens out.
- **(B) per-route**: each authenticated route renders
  `<AppShell>{...page}</AppShell>` at its top level; auth screens
  don't.

We pick **(B)**. The auth surface (`/login`, `/signup`,
`/confirm`, `/forgot-password`, `/reset-password`,
`/invitations/$token/accept`) has a deliberately minimal layout
(`AuthLayout`) — wrapping it in the dashboard shell would force a
sidebar render before the user can sign in, which is both wrong
visually and a waste of the `/v1/tenants/me` request the sidebar
makes.

Per-route opt-in also keeps the router file flat: no nested
`<Route>` shenanigans, no `beforeLoad` plumbing to swap layouts.

### D3 — Sidebar state persisted to `localStorage`

The collapse state (`expanded` vs `collapsed`) persists across
reloads under key `nica-erp:sidebar-state`. Rationale:

- Operators iterate inside a single tenant for long sessions. Their
  sidebar preference is stable across reloads.
- The state is purely UX — losing it on `queryClient.clear()`
  during a tenant switch would re-expand the sidebar mid-flow,
  which is annoying without buying any consistency.
- It's a single string (`"expanded"` | `"collapsed"`), no PII, no
  tenant-scope. Plain `localStorage` is fine.

Mobile drawer state is **session-only** (a React `useState`) — a
drawer should always start closed when the user navigates.

### D4 — Placeholder cards advertise the missing sprint

Three styles considered for the `/sales`, `/inventory`, `/reports`,
`/settings` placeholders:

- **(A)** Empty `<Card>` with title only — too cryptic; first-time
  users don't know whether the page is broken or empty.
- **(B)** Lorem-ipsum filler — actively misleading and indexable
  by screenshot reviewers.
- **(C)** Card titled with the nav label, a `Coming soon.`
  description, and a one-line hint of what the section will host
  (e.g. `"Inventory · Coming soon. · Products, kardex and stock
  movements will land here."`). No sprint numbers in the UI.

We pick **(C)**. The placeholders are intentional WIP markers, not
roadmap statements: they tell whoever opens the page that the
section is coming and what kind of content to expect, without
leaking internal scheduling.

The `/dashboard` placeholder is a separate beast (see D5).

### D5 — `/dashboard` ships KPI/chart/table shapes, not content

`/dashboard` is the only placeholder with a richer skeleton. It
renders:

- Four card slots in a 2×2 grid (`<Card>` with title `"Placeholder
  KPI"` and a `<Skeleton>` body) — the shape sprints 04-08 will fill
  with revenue, receivables, stock-at-risk, top-selling-product
  totals.
- One chart-shaped panel — a `<Card>` containing a
  `<Skeleton className="h-64">` and a label `"Trend chart
  placeholder"`.
- One table-shaped panel — a `<Card>` containing a labelled
  `<Skeleton>` block sized like a 5-row table.

These slots use the same `<Card>` from
`components/ui/card.tsx` that sprints 04-08 will hydrate, so the
hand-off is a literal child swap: the slot's `<Skeleton>` is
replaced by a real `<ChartArea/>` or `<DataTable/>` without
changing the surrounding markup. No fake numbers, no random-data
charts.

### D6 — `/me` is a redirect, not deleted

We could:

- **(A)** Delete `apps/web/src/routes/me.tsx` and let the router
  404 on `/me`.
- **(B)** Keep `apps/web/src/routes/me.tsx` and replace its
  content with the new `/account` view.
- **(C)** Replace `apps/web/src/routes/me.tsx` with a redirect to
  `/account` (`beforeLoad: () => throw redirect({ to: "/account" })`).

We pick **(C)**. Reasons:

- Existing vitest tests for `/me` continue to work after a
  one-line edit: `expect(router.state.location.pathname).toBe(
  "/account")` instead of `"/me"`.
- Any link buried in test fixtures, log lines, or the README that
  says `/me` still arrives where the user expects.
- We avoid splitting the new account screen across two route
  files (`/me` and `/account`) just for backwards compat.

Deleting `/me` outright is rejected because the redirect is
cheaper than the audit of where `/me` might still be referenced.

## Risks

- **Bundle size of the inlined sidebar.** Without Sheet/Dialog the
  sidebar primitives weigh under 5 KB gzipped. Acceptable.
- **Theme contrast on the sidebar.** The `--sidebar-foreground` /
  `--sidebar-accent-foreground` tokens were defined in sprint 02
  but never used in a real component. We verify both light and
  dark themes in the implementation step; a failing contrast adds
  a one-line CSS tweak rather than a token change.
- **Mobile drawer focus-trap.** The bare-bones drawer doesn't trap
  focus or restore it on close. Acceptable for MVP; the mobile
  surface is not the operator's primary device per
  [`docs/01-overview.md`](../../../docs/01-overview.md). Sprint 09's
  MVP-validation pass revisits.

## Out of scope

- Sidebar permission gating per nav item (sprint 04+ as real
  screens ship).
- Operator-controllable sidebar layouts, pinned items, recent
  searches.
- Charts and tables with real data (each bounded context owns its
  own delivery).
- A `/me` API contract change. The backend `/v1/me` is unchanged.
