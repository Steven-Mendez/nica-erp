## Why

Today the SPA's `route-guard.ts` redirects to `/tenants` (the empresa
picker) **only when `me.active_tenant === null`**. The very first time
an operator signs up + creates an empresa, `SwitchActiveTenant` mints
a fresh JWT whose `custom:active_tenant` is the newly created empresa
id — so every subsequent login lands directly on `/dashboard`,
skipping the picker.

That breaks two real expectations in hands-on testing
([operator feedback, 2026-05-28](#)):

1. An operator with **one or more empresas** still wants a "pick an
   empresa" landing screen after login, the way Supabase forces
   `Your Organizations` between sign-in and the project workspace.
   Without it, the SPA hides the active empresa behind the sidebar's
   `TenantSwitcher` chip — discoverable on day three, invisible on
   day one.
2. From the dashboard, **switching empresas should be one click
   away**. Today the sidebar's `TenantSwitcher` is the only path,
   and it lives behind a header chip that is easy to miss when the
   sidebar is collapsed.

This change makes `/tenants` the canonical post-login landing screen
(matching Supabase's `Your Organizations`) and surfaces a persistent
"Cambiar empresa" entry point on every authenticated route so the
operator can return to the picker without thinking about it.

## What Changes

### Route guard — `/tenants` becomes the canonical post-login landing

- `apps/web/src/lib/route-guard.ts`: introduce a new step between
  the membership probe (currently §3) and the active-tenant probe
  (currently §4). The new step asks: **"has the operator confirmed
  the active empresa in this browser session?"**
  - On a fresh session the answer is *no* → redirect to `/tenants`
    even when `me.active_tenant` is already set on the JWT.
  - Selecting an empresa from the picker (or clicking `Continuar`
    on the only available card) flips a session-scoped flag (e.g.
    `sessionStorage["nica-erp:picker-confirmed"] = "1"`) and lets
    the guard pass through to `/dashboard`.
  - The flag is intentionally session-scoped (not persisted in
    `localStorage`) — a new tab / new browser session restarts the
    picker requirement, matching Supabase's behaviour.
- The probe is bypassed for routes already on the `TENANT_EXEMPT`
  list (`/welcome`, `/onboarding`, `/tenants`, `/tenants/new`,
  `/account`, `/health`), since those flows by definition let the
  operator self-serve into the picker.

### Empresa picker — refactor `/tenants/index.tsx` to match Supabase

- Header: "Tus empresas" (`useDocumentTitle("Tus empresas")`).
- Search input (Spanish placeholder "Buscar una empresa…")
  filtering the cards by `name` (case-insensitive substring match).
- Grid of `<Card>` tiles, three per row at `md`, two at `sm`, one
  on mobile. Each card shows:
  - empresa initials avatar (first two letters of `name`).
  - empresa `name` and the member's role badge (`Owner`, `Admin`,
    `Contador`, …) on the right.
  - subtitle line — count of pending invitations the operator
    issued in that empresa (e.g. `2 invitaciones pendientes`).
    Pulled from the existing `GET /v1/tenants/{id}/invitations`
    endpoint — no new backend.
- Top-right `+ Nueva empresa` CTA linking to `/tenants/new`.
- Click on a card calls `useSwitchTenantMutation`, flips the
  session-scoped picker-confirmed flag, and navigates to
  `/dashboard`.
- Empty state (no memberships) reuses the existing alert + link
  to `/tenants/new`.

### Persistent "Cambiar empresa" affordance

- `apps/web/src/components/app-sidebar/tenant-switcher.tsx`: the
  switcher's menu MUST list a `Cambiar empresa` row at the bottom
  that navigates to `/tenants` (and clears the session
  picker-confirmed flag so the picker is fully owned by the
  operator). The row is always rendered, even when the operator
  belongs to a single empresa.
- `apps/web/src/components/app-shell/site-header.tsx`: the
  breadcrumb already shows "Empresas" for `/tenants` — verify the
  existing path renders. No new affordance on the header.

### Backend

- No backend changes. `GET /v1/tenants/me`,
  `POST /v1/tenants/{id}/switch`, and
  `GET /v1/tenants/{id}/invitations` all exist from sprint 03.
- No migration. No new endpoint. No ADR.

### Tests

- `apps/web/tests/unit/lib/route-guard.test.ts` — extend with a
  case asserting that the picker-confirmed flag gates the
  active-tenant probe; clearing the flag forces `/tenants`.
- `apps/web/tests/unit/routes/tenants-index.test.tsx` — new:
  (a) renders the picker title, search input and `+ Nueva
  empresa` CTA; (b) typing in the search box filters the cards;
  (c) clicking a card calls the switch mutation and sets the
  session flag; (d) the empty-state alert appears with zero
  memberships.

## Capabilities

### New Capabilities

- `empresa-picker`: the post-login empresa selection screen and
  the route-guard policy that requires explicit confirmation
  before reaching `/dashboard`. The single-card variant is
  intentionally rendered (matching Supabase) — auto-skip when
  exactly one empresa exists is **not** part of this change so
  the picker stays predictable.

### Modified Capabilities

- `frontend-shell`: the sidebar's `TenantSwitcher` adds a
  persistent `Cambiar empresa` entry that navigates back to
  `/tenants`. The collapsed sidebar variant SHALL still expose
  the entry through the chip's hover popover.

## Impact

- Affected code:
  - `apps/web/src/lib/route-guard.ts` (new probe step).
  - `apps/web/src/routes/tenants/index.tsx` (Supabase-style
    refactor).
  - `apps/web/src/components/app-sidebar/tenant-switcher.tsx`
    (persistent back link).
  - `apps/web/src/features/tenants/api/hooks.ts` (no surface
    change — verify the existing switch mutation already
    invalidates the picker-relevant queries).
- Affected tests:
  - `apps/web/tests/unit/lib/route-guard.test.ts` — new branch
    for the picker-confirmed flag.
  - `apps/web/tests/unit/routes/tenants-index.test.tsx` — new file.
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — append a "Sprint
    follow-up — Force tenant picker on every session (sprint
    3.13, 2026-05-28)" section.
  - No ADR. The picker-confirmed flag is a UX policy, not an
    architectural decision, and reuses the existing
    `route-guard` mechanism.
- Affected dependencies: none.
- Affected env: none — the picker-confirmed flag is
  session-scoped JS state, not a new env var.
- Affected backend: none.
- Out of scope: auto-skip when exactly one empresa exists,
  multi-empresa keyboard shortcuts, recently-used reordering,
  empresa logos / avatars beyond the two-letter initials, and any
  RBAC change. Those land under separate proposals if the
  operator requests them after this picker ships.

## Carry-over (2026-05-30)

Blocked on operator browser smoke (multi-tab, sign in / sign out, sidebar navigation). Code + unit tests landed; manual verification items are tracked as pre-sprint-04 tasks 10 and 11.
