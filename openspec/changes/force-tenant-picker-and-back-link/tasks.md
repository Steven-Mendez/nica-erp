## 1. Sprint doc

- [x] 1.1 Append "Sprint follow-up — Force empresa picker on every session (sprint 3.13, 2026-05-28)" to `docs/sprints/03-tenants-and-rls.md` after the existing 3.12 follow-up. Cover motivation (operator report — picker hidden behind sidebar chip on day one), scope (one file in `lib/`, one route, one sidebar component, two tests), explicit non-goals (no auto-skip for single-empresa operators, no cross-session memory of the last picked empresa, no logo / branding field).

## 2. Picker-confirmed session flag

- [x] 2.1 In `apps/web/src/lib/route-guard.ts`, declare a module-scope constant `const PICKER_FLAG_KEY = "nica-erp:picker-confirmed";` and a small helper `function isPickerConfirmed(): boolean { return typeof window !== "undefined" && window.sessionStorage.getItem(PICKER_FLAG_KEY) === "1"; }`.
- [x] 2.2 Add `function setPickerConfirmed(): void` and `function clearPickerConfirmed(): void` helpers next to the constant. Export both helpers + the constant so other modules (logout, TenantSwitcher) reuse the same key.
- [x] 2.3 Wire `setPickerConfirmed()` in the `useSwitchTenantMutation`'s `onSuccess` handler in `apps/web/src/features/tenants/api/hooks.ts`. Wire `setPickerConfirmed()` in the `useCreateTenantMutation`'s post-switch success path (the wizard already calls switch — flip the flag in the same callback so `/tenants/new` → switch → dashboard works without a forced trip back through the picker).
- [x] 2.4 Wire `clearPickerConfirmed()` in `useLogoutMutation`'s `onSuccess` handler in `apps/web/src/features/auth/api/hooks.ts`.

## 3. Route guard probe

- [x] 3.1 In `nextRouteForCurrentState`, insert a new step **after** the membership probe and **before** the active-tenant probe: if `!isPickerConfirmed() && !TENANT_EXEMPT.has(pathname)` → `return "/tenants"`.
- [x] 3.2 Leave the existing active-tenant probe in place as a defensive fallback (covers the case where the flag is set but the JWT lost `custom:active_tenant` after a refresh).
- [x] 3.3 Update the `TENANT_EXEMPT` set if needed so `/tenants` itself does not loop redirect. It already includes `/tenants` and `/tenants/new` per the current code.

## 4. Empresa picker route (`/tenants/index.tsx`)

- [x] 4.1 Rewrite the page header: replace the existing title block with a flex row containing `<h1 className="text-2xl font-semibold">Tus empresas</h1>` on the left and a `<Button asChild><Link to="/tenants/new">+ Nueva empresa</Link></Button>` on the right.
- [x] 4.2 Below the header, render an `<Input>` with `placeholder="Buscar una empresa…"` bound to a local `useState<string>("")`. The filtered list is `memberships.items.filter(m => m.name.toLowerCase().includes(query.toLowerCase()))`.
- [x] 4.3 Replace the existing list with a responsive grid: `<div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">`. Render one `<Card role="button" tabIndex={0}>` per filtered membership.
- [x] 4.4 Each card renders:
  - Initials avatar: `<div className="size-9 rounded-md bg-muted text-sm font-semibold grid place-items-center">{initials}</div>` where `initials = name.split(/\s+/).slice(0, 2).map(s => s.charAt(0).toUpperCase()).join("")`.
  - Empresa `name` and role badge (`<Badge>`) on the same row.
  - Pending-invitation subtitle pulled from `useTenantInvitationsQuery(membership.tenantId)` — render `{count} invitaciones pendientes` only when `count > 0`. Skip the line entirely when the query is loading (avoid layout shift).
- [x] 4.5 On card activation (`onClick` and `onKeyDown` for Enter/Space), call `switchMut.mutate(tenantId, { onSuccess: () => { setPickerConfirmed(); navigate({ to: "/dashboard" }); } })`. Disable all cards while any switch is pending.
- [x] 4.6 Keep the existing empty-state `<Alert>` for zero memberships, with the `Crear empresa` link to `/tenants/new`. Preserve Spanish copy.

## 5. Persistent "Cambiar empresa" affordance

- [x] 5.1 In `apps/web/src/components/app-sidebar/tenant-switcher.tsx`, add a `<Separator className="my-1" />` followed by a row that, on click, calls `clearPickerConfirmed()` then `navigate({ to: "/tenants" })`. The row's copy is `Cambiar empresa`, prefixed with a `<Building2 />` icon (already imported elsewhere in the file) for visual parity with the empresa rows above.
- [x] 5.2 Ensure the row is rendered for *every* authenticated operator — including those with a single empresa. The existing single-empresa branch needs to be widened to always emit the popover (today it may render the chip as a non-clickable label).
- [x] 5.3 Verify the collapsed sidebar variant still exposes the entry through the chip's hover popover. If the existing chip-only collapsed mode skips the popover, switch to a `<Tooltip>` + `<Popover>` so the affordance stays one click away.

## 6. Tests

- [x] 6.1 Update `apps/web/tests/unit/lib/route-guard.test.ts`:
  - (a) Without the picker flag and with a non-null `me.active_tenant`, the guard redirects `/dashboard` to `/tenants` (new case — was previously a pass-through).
  - (b) With the picker flag set, the guard passes through to `/dashboard`.
  - (c) The flag does NOT trigger a redirect for routes in `TENANT_EXEMPT` (e.g. `/account`, `/tenants`).
- [x] 6.2 New file `apps/web/tests/unit/routes/tenants-index.test.tsx`:
  - (a) Picker renders `Tus empresas` title, search input, and `+ Nueva empresa` button.
  - (b) Typing in the search input filters the cards (3 memberships → typing `acme` shows 2).
  - (c) Clicking a card calls `useSwitchTenantMutation` with the empresa id; on success, `sessionStorage["nica-erp:picker-confirmed"]` becomes `"1"` and the navigate spy is called with `{ to: "/dashboard" }`.
  - (d) The empty-state `<Alert>` renders when memberships is empty.
- [x] 6.3 Extend or add `apps/web/tests/setup.ts` to call `window.sessionStorage.clear()` in `beforeEach`, mirroring the existing `localStorage.clear()` (already in place per `tests/unit/components/app-sidebar/sidebar-context.test.tsx`).
- [x] 6.4 Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`. All three must pass.

## 7. Smoke

- [ ] 7.1 In the dev server, log in as a single-empresa operator. Verify the SPA lands on `/tenants` with one card visible and the `+ Nueva empresa` button on the right. Click the card → SPA navigates to `/dashboard`.
- [ ] 7.2 From `/dashboard`, open the sidebar's `TenantSwitcher` and click `Cambiar empresa`. Verify the SPA navigates to `/tenants`.
- [ ] 7.3 Refresh the tab. The flag is preserved (in-tab navigation, not new session) — the SPA can re-enter the dashboard without re-confirming.
- [ ] 7.4 Open a new browser tab (same origin), sign in, verify the picker re-appears.
- [ ] 7.5 Log out from the existing tab; sign back in; verify the picker re-appears.

## 8. Forward-compat checks

- [ ] 8.1 Confirm `/onboarding`, `/welcome`, `/tenants/new`, `/invitations/$token/accept` still pass through without being redirected to the picker (TENANT_EXEMPT coverage). Visit each in dev with the picker flag unset.
- [x] 8.2 `openspec validate force-tenant-picker-and-back-link` exits 0.
