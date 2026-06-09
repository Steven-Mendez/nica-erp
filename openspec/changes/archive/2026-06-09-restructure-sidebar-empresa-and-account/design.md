## Context

Sprint 03 shipped the backend tenants context end-to-end:

- `Tenant` aggregate + fiscal-data fields (sprint 3.11 made every
  fiscal field optional per ADR-0034).
- `Membership` + `Invitation` aggregates + the `tenant_members_self`
  RLS policy.
- The full `/v1/tenants/*` HTTP surface (create / list / get /
  patch / switch + members + invitations).
- The RBAC catalog (`tenant:read`, `tenant:write`, `members:read`,
  `members:invite`, `members:update-role`, `members:remove`) and
  the `require(...)` FastAPI dependency.

The SPA surface that consumes those capabilities lags. Concretely:

| Backend capability | SPA today |
| --- | --- |
| `GET /v1/tenants/me` | ✅ picker at `/tenants` |
| `POST /v1/tenants` | ✅ `/tenants/new` |
| `POST /v1/tenants/{id}/switch` | ✅ from picker + create flow |
| `GET /v1/tenants/{id}` | ⚠️ only the soft-creation banner reads it |
| `PATCH /v1/tenants/{id}` | ❌ no UI |
| `GET /v1/tenants/{id}/members` | ⚠️ deep route `/tenants/$id/members`, no nav entry |
| `PATCH /v1/tenants/{id}/members/{user_id}` | ⚠️ used inside the deep route |
| `DELETE /v1/tenants/{id}/members/{user_id}` | ⚠️ used inside the deep route |
| `GET /v1/tenants/{id}/invitations` | ⚠️ used inside the deep route |
| `POST /v1/tenants/{id}/invitations` | ⚠️ used inside the deep route |
| `DELETE /v1/tenants/{id}/invitations/{invitation_id}` | ⚠️ used inside the deep route |

The deep route `/tenants/$id/members` is the only home for member
+ invitation management, and it is **unreachable from the
sidebar** — operators only land there if they followed a deep
notification link. The information-architecture gap is the
problem this change fixes.

The operator's report also surfaced the **scope confusion**
between empresa-scoped routes (Settings, Inventario) and
identity-scoped routes (Account). Promoting `/account` out of the
AppShell — same place the picker lives — makes the boundary
visible.

## Goals / Non-Goals

**Goals:**

- Make every empresa-scoped capability reachable from a single
  `Empresa` parent in the sidebar.
- Make the empresa-vs-account scoping visible: account renders
  outside the AppShell chrome, just like the tenant picker.
- Operate the empresa management surface on the **active**
  empresa derived from `me.active_tenant`, not on a URL `$id`
  segment. Switching empresas from the sidebar's switcher seam
  -lessly retargets every empresa-scoped page.
- Preserve every existing permission gate: the new pages reuse
  `useHasPermission(...)` to render or hide affordances.

**Non-Goals:**

- Implement the wired fiscal-data editor at `/empresa/configuracion`
  (placeholder copy holds until a follow-up sprint with a real
  PATCH form). The PATCH endpoint exists today; the spec just
  doesn't require a UI yet.
- Add per-user permission overrides. The RBAC catalog stays
  role-driven; granular grants are documented as a backend gap and
  deferred.
- Touch the picker layout / behaviour delivered by
  [[force-tenant-picker-and-back-link]]. The two changes are
  composable: this change renames + reorganises sidebar entries
  while the picker change owns `/tenants` itself.
- Move the `Sales` / `Inventory` / `Reports` / `Settings`
  placeholder routes (those stay as flat AppShell children).

## Decisions

### `Empresa` is a multi-level entry, not a tab strip

The sidebar's existing flat list (`Resumen`, `Ventas`,
`Inventario`, `Reportes`, `Settings`) reads as one section. A
multi-level `Empresa` entry preserves the reading rhythm while
exposing the sub-pages. Alternatives considered:

- **Tab strip inside `/empresa`** — rejected because the tabs
  would be invisible from `/dashboard`; the sidebar nav is the
  one place we know every operator scans.
- **Three flat top-level items (`Usuarios`, `Empresa`,
  `Configuración`)** — rejected because the empresa name + role
  badge needs a header to live on; without it, `Usuarios` reads
  as a global users list.

The chevron toggle's open/closed state persists under
`localStorage["nica-erp:sidebar-empresa-open"]` so power users
who keep it expanded stay expanded; collapsed users stay
collapsed.

### Route prefix is `/empresa/*`, not `/tenants/$tenantId/*`

Two reasons:

1. The active empresa is already canonical — `me.active_tenant`
   resolves to a UUID. Encoding the same UUID in the URL adds
   noise without adding semantic value (the SPA never lets the
   operator navigate into a non-active empresa's management
   surface — they switch first via the picker).
2. The router doesn't need a `$tenantId` loader; pages call the
   hooks with `me.active_tenant` and let the existing query
   cache key it.

The migration path is to remove `/tenants/$id/members` (the
single deep route that used the `$tenantId` segment). The picker
+ create routes (`/tenants`, `/tenants/new`) stay because they
operate above the empresa context.

### `/account` is identity-scoped — no AppShell

The `/account` view shows the operator's email, display name,
locale, timezone, the active empresa, and the operator's
permissions in that empresa. Three of those (email, display name,
locale/timezone) are identity-scoped; they survive an empresa
switch. Rendering `/account` inside the AppShell implies it lives
under the active empresa.

The chosen chrome is an `<IdentityLayout>` mirror of
`AuthLayout`: a thin top bar with the empresa-switcher chip on
the right and a `← Volver` link on the left that routes to the
last visited AppShell route (kept in
`sessionStorage["nica-erp:last-app-route"]` and updated on every
AppShell route mount). No sidebar.

### Surfacing the invitation list under `Empresa → Usuarios`

The owner's view at `Empresa → Usuarios` issues
`GET /v1/tenants/{active}/invitations` which works under the
owner's tenant context (the RLS policy passes because
`app.tenant_id` is set by the tenant middleware). The accept
flow (which has the GUC bug under
[[test-backfill-and-e2e-tooling]] §3.2) is the *invitee's* flow
and is not on `Empresa → Usuarios`. So this change can ship
without depending on the accept-flow fix.

### Permission assignment = role change (for now)

The operator's report mentioned "asignar permisos". This change
maps that to the existing role-change flow:

- The `Empresa → Usuarios` page lists members with their role.
- Operators with `members:update-role` can change a member's
  role inline via a `<Select>`.
- Each role's permission set is the catalog
  `DEFAULT_ROLE_PERMISSIONS` from
  `apps/api/src/shared_kernel/permissions/catalog.py`.

If the operator wants **granular per-user grants** (e.g. "this
salesperson also gets `members:read`"), that is a new backend
feature documented as a gap below — not landed here.

## Backend gaps surfaced by this change

### Gap 1 — Per-user permission overrides

Today the RBAC catalog is fixed:

```python
DEFAULT_ROLE_PERMISSIONS = {
  "viewer":      frozenset({"tenant:read"}),
  "salesperson": frozenset({"tenant:read"}),
  "accountant":  frozenset({"tenant:read", "members:read"}),
  "admin":       frozenset({...}),
  "owner":       frozenset({...}),
}
```

The `Actor.permissions` resolver reads only this mapping. There
is no way to grant or revoke a single permission for a single
member without changing their role. If the SPA wants a `Edit
permissions` dialog with per-permission toggles, the backend
needs:

- A new table `tenant_member_permissions` with columns
  `tenant_id`, `user_id`, `permission_code`, `granted` (boolean),
  `created_at`, plus the standard per-tenant RLS policy.
- A migration seeding nothing (empty by default — every member's
  effective set is still the role's catalog until an override is
  written).
- Two endpoints:
  `GET /v1/tenants/{id}/members/{user_id}/permissions` and
  `PUT /v1/tenants/{id}/members/{user_id}/permissions` (body:
  `{ grants: [{code, granted}] }`). Both gated by a new
  `members:update-permissions` catalog entry that defaults to the
  owner + admin set.
- An `Actor` resolver update that unions the role catalog with
  the overrides.

This change does **not** implement the gap. The spec captures it
so the work can be scheduled.

### Gap 2 — `POST /v1/invitations/accept` does not set `app.tenant_id`

Already tracked in
[[test-backfill-and-e2e-tooling]] §3.2; surfaced here for
completeness. The owner-facing UI in this change does not depend
on it (the owner lists invitations from inside their own tenant
context). The invitee's accept page (`/invitations/$token/accept`)
already exists and continues to fail at runtime until the GUC
fix lands.

## Risks / Trade-offs

- **Bigger sidebar primitives surface** — adding
  `SidebarMenuSub` increases the components we own. The
  alternative was an external `Collapsible` package; sticking
  with the existing pattern (handcrafted shadcn-style primitives)
  is cheaper to evolve.
- **Two routing surfaces for the same UUID** —
  `/empresa/usuarios` operates on `me.active_tenant`, while
  `/tenants/$id/members` was hand-keyed. Deleting the second one
  means deep notifications cannot include the empresa id in the
  URL; they must include a `?tenant=<id>` query and trigger a
  switch first. The notification flow ships in a later sprint,
  so this change accepts that trade-off.
- **AppShell vs IdentityLayout duplication** — the new
  `<IdentityLayout>` adds a second top-level layout. The
  duplication is intentional: the two surfaces have different
  affordances and conflating them obscures the scope boundary.

## Migration Plan

1. Land the new files (`empresa/*` routes, `IdentityLayout`,
   `SidebarMenuSub` primitives, hooks).
2. Update the router to register the new routes and to remove the
   old `/tenants/$id/members` route.
3. Update `account.tsx` to drop `<AppShell>` and wrap in
   `<IdentityLayout>`.
4. Update the sidebar's NAV_ITEMS to point at the new structure.
5. Delete `apps/web/src/routes/tenants/members.tsx` and
   `apps/web/src/routes/empresa/editar.tsx` (folded into
   `configuracion.tsx`).
6. Run the test suite + smoke on the empresa-scoped flows.

No backend change, no migration, no feature flag.

## Open Questions

- Should `Empresa → Vista general` render the fiscal Revisión
  card from sprint 3.10 verbatim, or a slimmer summary tailored
  for the dashboard chrome? Default = verbatim (the four-section
  card is already polished); revisit if the spacing collides.
- Should the `Empresa` parent entry be hidden entirely for
  operators with `viewer` role (whose permissions don't include
  `members:read` or `tenant:write`)? Currently the proposal keeps
  the parent visible and gates affordances inside. Revisit if
  product wants a cleaner sidebar for low-permission operators.
