## Context

`apps/web/src/lib/route-guard.ts` runs from every authenticated
route's `beforeLoad`. Its current shape:

1. Fetch `/v1/me`.
2. If `display_name === null` → `/welcome`.
3. Fetch `/v1/tenants/me`. If `items.length === 0` → `/onboarding`.
4. If `me.active_tenant === null` and the target is not on
   `TENANT_EXEMPT` → `/tenants`.
5. Otherwise pass through.

In the field, an operator who has already created an empresa lands
on `/dashboard` on every subsequent login because step 4 sees a
non-null `active_tenant` (their JWT was issued *after* the first
`SwitchActiveTenant`, so the claim is hydrated). The picker at
`/tenants` becomes a screen the operator never re-encounters
without manually typing the URL.

Supabase's reference UI (`Your Organizations`) is the inverse: every
new browser session forces the operator through the picker, and a
"Switch organization" entry inside the in-app menu makes returning
to it cheap. The operator that filed the report is asking for the
same behaviour.

## Goals / Non-Goals

**Goals:**

- A fresh browser session (new window, new tab opened from the
  bookmark, post-logout) always lands on `/tenants` after
  authentication, regardless of whether the JWT already carries
  `custom:active_tenant`.
- Selecting an empresa from the picker is the moment the operator
  *enters* the workspace. Until that click, the dashboard / sales /
  inventory routes redirect back to `/tenants`.
- A persistent "Cambiar empresa" entry in the sidebar's
  `TenantSwitcher` returns the operator to the picker without
  hunting through menus.
- The picker visual matches the Supabase reference: search box,
  grid of cards, `+ Nueva empresa` CTA, predictable single-card
  rendering when only one empresa exists.

**Non-Goals:**

- Auto-skip the picker when exactly one empresa exists. The
  reference UI does not do this and the operator's report
  specifically asks for the screen even with a single empresa.
- Remember the last picked empresa across sessions (e.g. via
  `localStorage`). Cross-session persistence reintroduces the
  same "hidden active empresa" problem the user reported.
- Add an empresa logo / branding field. The two-letter initials
  avatar is sufficient for the MVP.
- Touch the backend or the RBAC catalog. The picker is a pure
  frontend policy change.

## Decisions

### Picker-confirmed flag lives in `sessionStorage`

`sessionStorage["nica-erp:picker-confirmed"]` is set to `"1"` the
moment the operator confirms an empresa from the picker (either by
clicking a card or by reaching `/tenants/new` and successfully
creating + auto-switching). The flag is read by the route guard's
new step and gates the pass-through to `/dashboard`.

Why `sessionStorage` (not `localStorage`, not in-memory):

- `sessionStorage` is automatically cleared when the tab is
  closed, which matches Supabase's "force picker on each browser
  session" behaviour without inventing our own lifecycle.
- It survives in-tab navigation (so clicking around the SPA does
  not re-trigger the picker), which an in-memory flag would not.
- It is **never persisted** beyond the tab, so an operator who
  closes the browser, walks away, and returns the next day will
  see the picker again — desirable for shared kiosks and matches
  the XSS-posture choice from
  [`docs/06-security-model.md`](../../../docs/06-security-model.md)
  for tokens (no long-lived sensitive state in `localStorage`).

The flag is cleared by:

- `useLogoutMutation`'s `onSuccess` callback (so re-login forces
  the picker).
- The "Cambiar empresa" entry on the `TenantSwitcher` (so
  navigating back to the picker is a single click and reliably
  re-shows the screen).

### Route-guard probe order

The new step lands **between** the membership probe and the
active-tenant probe so the picker takes precedence over the
"missing active_tenant" path. Pseudocode:

```ts
if (me === null) return "/login";
if (me.display_name === null && !WELCOME_EXEMPT) return "/welcome";

const memberships = await getMyTenants();
if (memberships.items.length === 0) return "/onboarding";

const pickerConfirmed = sessionStorage.getItem(PICKER_FLAG) === "1";
if (!pickerConfirmed && !TENANT_EXEMPT.has(pathname)) {
  return "/tenants";
}

if ((me.active_tenant ?? null) === null && !TENANT_EXEMPT.has(pathname)) {
  return "/tenants";
}

return null;
```

The active-tenant probe stays as a defensive fallback for the
narrow case where the operator confirmed the flag but then the
JWT got rotated and lost `custom:active_tenant` (e.g. token
refresh after the operator was removed from the empresa).

### Single-card variant is intentional

When the operator belongs to exactly one empresa, the picker
still renders that single card. Auto-skip would re-create the
"hidden active empresa" problem the report flagged. The card is
a deliberate one-click confirmation, not friction.

### `Cambiar empresa` entry on `TenantSwitcher`

The sidebar's `TenantSwitcher` already opens a popover listing the
operator's empresas. This change appends a `Cambiar empresa` row
at the bottom (after a `<Separator />`) that:

1. Clears `sessionStorage["nica-erp:picker-confirmed"]`.
2. Navigates to `/tenants` via `router.navigate`.

The collapsed sidebar variant keeps the chip's hover popover; the
entry stays visible there.

## Risks / Trade-offs

- **Extra click on every session** — operators with a single
  empresa now click "Continuar" once per browser session before
  reaching the dashboard. The report explicitly accepts that cost
  in exchange for the picker's discoverability.
- **`sessionStorage` is per-tab** — opening the same SPA in two
  tabs forces the picker in each tab. This is what Supabase does
  and matches the report's mental model. No follow-up.
- **Test stability around `sessionStorage`** — unit tests must
  clear the flag in `beforeEach` to avoid order-dependence. The
  shared `setup.ts` already runs a `localStorage.clear()`; we add
  the `sessionStorage.clear()` mirror.

## Migration Plan

This is a UX policy change behind the existing route guard. There
is no data migration and no backend deploy. On the first SPA
release after the change lands:

1. The first authenticated request on the existing tab finds no
   `picker-confirmed` flag → redirects to `/tenants`.
2. The operator clicks an empresa card → flag is set → routes
   continue as usual.

No flag, feature toggle, or staged ramp is needed; the change is
inherently reversible (delete the new probe step + the
`sessionStorage` flag handling).

## Open Questions

- Should the `Cambiar empresa` entry also expose a keyboard
  shortcut (e.g. `⌘ ;`)? Deferred — not in the operator's report.
- Should the picker show a "recently active" tag on the empresa
  the operator most recently confirmed? Deferred — adds
  persistent state across sessions, which this change deliberately
  avoids.
