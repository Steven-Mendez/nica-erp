## Why

The current sidebar layout in `apps/web/src/components/app-sidebar/`
treats `/tenants` as a flat top-level link sitting next to `Ventas`,
`Inventario`, `Reportes`, `Settings`. Hands-on testing surfaced
three problems:

1. `/tenants` is conceptually a **picker**, not a section inside the
   dashboard — it lives above the empresa context the operator just
   selected. Rendering it inside the AppShell next to `Ventas` is
   misleading: clicking it does not "open empresas", it abandons the
   active empresa.
2. There is no way to reach **the empresa-scoped management
   surface** — listing the operator's members, the pending
   invitations they issued, the fiscal-data editor — from a single
   nav node. Today `/tenants/$id/members` exists but is reachable
   only by typing the URL or by clicking a deep link from a
   notification.
3. `/account` belongs to the **operator's identity**, not to a
   specific empresa. It currently sits next to empresa-scoped
   routes (`Settings`, `Inventario`), implying it is empresa-scoped
   when in fact it persists across empresa switches.

The fix is to restructure the navigation so:

- `Empresa` becomes a single **multi-level** sidebar entry with the
  empresa-scoped sub-routes (Usuarios, Invitaciones, Configuración)
  underneath. The empresa name + role badge moves to the section's
  header label.
- `/tenants` (the picker) and `/account` (the operator's profile)
  both render **outside** the AppShell — same shell as `/login`,
  `/welcome`, `/onboarding`. They are reachable from the sidebar
  (via the empresa switcher's `Cambiar empresa` row and the user
  menu's `Mi cuenta` entry) but they do not render the dashboard
  chrome.
- The existing flat `/tenants/$id/members.tsx` route is replaced by
  a nested route group at `/empresa/usuarios`, `/empresa/invitaciones`,
  `/empresa/configuracion` that operates on the **active**
  empresa — there is no `$tenantId` segment because the active
  empresa is always derived from `me.active_tenant`.

This is the sprint 3.14 follow-up — it closes the gap between what
sprint 03's backend already supports (`GET /v1/tenants/{id}/members`,
`PATCH /v1/tenants/{id}`, the invitation endpoints, the RBAC
permission catalog) and what the SPA exposes to operators today.

## What Changes

### Sidebar — multi-level `Empresa` entry

- Add a new `<SidebarMenuSub>` primitive to
  `apps/web/src/components/app-sidebar/sidebar.tsx` (mirrors the
  upstream shadcn shape: an inner `<ul>` rendered under a parent
  item with a chevron toggle). The primitive MUST support a
  `defaultOpen` boolean prop persisted under
  `localStorage["nica-erp:sidebar-empresa-open"]` so the section
  remembers its open/closed state across reloads.
- `apps/web/src/components/app-sidebar/app-sidebar.tsx`: replace
  the `{ label: "Tenants", to: "/tenants" }` row with a parent
  item `Empresa` (icon: `Building2`). Children:
  - `Vista general` → `/empresa` (default page, renders the
    fiscal summary card from sprint 3.11's "Completa los datos
    fiscales" banner family).
  - `Usuarios` → `/empresa/usuarios` (member list + pending
    invitations card on the same page).
  - `Configuración` → `/empresa/configuracion` (the editor
    placeholder at `/empresa/editar` is moved here; the wired
    PATCH form lands in a follow-up sprint).
- The collapsed sidebar variant collapses the section to the
  parent icon; a click expands the popover with the sub-items.

### Routes — nested empresa group under `/empresa/*`

- `apps/web/src/routes/empresa/index.tsx` — `<AppShell>` +
  fiscal summary card (RUC, régimen, municipio, dirección,
  retenedor badge, DGI vigencia). Reuses the Revisión-card layout
  from sprint 3.10 (the four-section pattern).
- `apps/web/src/routes/empresa/usuarios.tsx` — `<AppShell>` +
  two stacked cards:
  - **Miembros** — table from
    `GET /v1/tenants/{active_tenant_id}/members`, inline role
    `<Select>` gated by `members:update-role`, remove button gated
    by `members:remove`. Owner row is never editable.
  - **Invitaciones pendientes** — table from
    `GET /v1/tenants/{active_tenant_id}/invitations` filtered to
    `status === "pending"`. Cancel button gated by
    `members:invite`. A primary `+ Invitar` button opens a Dialog
    (email + role Select) gated by `members:invite`.
- `apps/web/src/routes/empresa/configuracion.tsx` — `<AppShell>` +
  the existing "Próximamente" placeholder copy until the wired
  editor lands. Replaces the current `apps/web/src/routes/empresa/editar.tsx`.
- The old `apps/web/src/routes/tenants/index.tsx`,
  `apps/web/src/routes/tenants/new.tsx`, and
  `apps/web/src/routes/tenants/members.tsx` keep serving the
  picker / onboarding paths (`/tenants`, `/tenants/new`); the
  `/tenants/$id/members` path is removed because the empresa
  group always operates on the active empresa.

### `/account` and `/tenants` move outside the AppShell

- `apps/web/src/routes/account.tsx` — replace `<AppShell>` with a
  lightweight chrome (`AuthLayout`-like wrapper or a new
  `<IdentityLayout>` that renders a top bar with the empresa
  switcher's "Cambiar empresa" + a `Volver` link, but no sidebar).
  The three identity cards (Profile / Empresa activa /
  Permisos) stay.
- `apps/web/src/routes/tenants/index.tsx` (the picker) already
  ships without `<AppShell>` for the empty-state flow; ensure the
  loaded-state also renders outside the AppShell to stay
  consistent with the picker proposal
  ([[force-tenant-picker-and-back-link]]).
- The sidebar's user menu (`nav-user.tsx`) gains a `Mi cuenta` row
  that navigates to `/account` from inside the AppShell — clicking
  it intentionally takes the operator out of the dashboard shell
  because the account view is identity-scoped.

### Frontend hooks — surface the existing endpoints

- `apps/web/src/features/tenants/api/hooks.ts` already exports
  `useMembersQuery`, `useInvitationsQuery`, `useInviteMemberMutation`,
  `useCancelInvitationMutation`, `useUpdateMemberRoleMutation`,
  `useRemoveMemberMutation`. Verify each one accepts a
  `tenantId` argument and that the new routes call them with
  `me.active_tenant`.
- Add `useUpdateTenantMutation` if missing (PATCH
  `/v1/tenants/{id}` already exists). Currently the SPA only has
  the create mutation.

### Tests

- `apps/web/tests/unit/components/app-sidebar/app-sidebar.test.tsx`
  — new: asserts the `Empresa` parent item renders with three
  child links and the chevron toggle.
- `apps/web/tests/unit/routes/empresa/usuarios.test.tsx` — new:
  asserts the member table renders, the role `<Select>` is gated by
  `members:update-role`, and the invitation cancel button is gated
  by `members:invite`.
- `apps/web/tests/unit/routes/empresa/index.test.tsx` — new:
  fiscal summary card renders RUC / régimen / municipio for a
  populated tenant; renders the "Completa los datos fiscales"
  banner for a soft-created tenant per ADR-0034.

### Documentation

- Append "Sprint follow-up — Empresa section + account scope
  split (sprint 3.14, 2026-05-28)" to
  `docs/sprints/03-tenants-and-rls.md`.
- No new ADR. Routing reshuffles + sidebar restructuring are
  inside [ADR-0009 — frontend stack](../../../docs/adr/0009-frontend-stack.md)
  and the empresa-vs-account scoping is the same boundary
  ADR-0022 already documents.

## Capabilities

### New Capabilities

- `empresa-section`: the nested `/empresa/*` route group, its
  multi-level sidebar entry, and the empresa-scoped management
  surfaces (Vista general, Usuarios + invitaciones,
  Configuración). The group always operates on
  `me.active_tenant`; no `$tenantId` URL segment.

### Modified Capabilities

- `frontend-shell`: the sidebar gains support for multi-level
  entries (parent + child rows + collapse persistence). The
  `Tenants` flat link is replaced by the `Empresa` parent.
  `/account` is removed from the AppShell-wrapped routes and
  rendered with a lightweight chrome instead.
- `tenants-http`: no new endpoints are required for the in-scope
  surface (the backend already exposes
  `GET /v1/tenants/{id}/members`,
  `GET /v1/tenants/{id}/invitations`,
  `POST /v1/tenants/{id}/invitations`,
  `DELETE /v1/tenants/{id}/invitations/{invitation_id}`,
  `PATCH /v1/tenants/{id}/members/{user_id}`,
  `DELETE /v1/tenants/{id}/members/{user_id}`,
  `PATCH /v1/tenants/{id}`). Two **backend gaps** are documented
  in the spec for follow-up sprints:
  - Per-user permission **overrides** (today the catalog is fixed
    by role; "assign permissions" in the proposal therefore means
    "change the user's role"; granular per-user grants need a
    new `tenant_member_permissions` table + endpoints).
  - The `POST /v1/invitations/accept` route does not set
    `app.tenant_id` from the verified token's tenant claim, so
    per-tenant RLS hides the row at acceptance time. The
    `Empresa → Usuarios` page surfaces the invitation **listing**
    (which works under the owner's tenant context); accept itself
    is the invitee's flow and the bug already tracked under
    [[test-backfill-and-e2e-tooling]] §3.2.

## Impact

- Affected code:
  - `apps/web/src/components/app-sidebar/sidebar.tsx` —
    `SidebarMenuSub` + `SidebarMenuSubButton` primitives.
  - `apps/web/src/components/app-sidebar/app-sidebar.tsx` — nav
    restructure (Empresa parent, Mi cuenta in user menu).
  - `apps/web/src/components/app-sidebar/nav-user.tsx` — add
    `Mi cuenta` entry.
  - `apps/web/src/routes/empresa/index.tsx`,
    `apps/web/src/routes/empresa/usuarios.tsx`,
    `apps/web/src/routes/empresa/configuracion.tsx` — new files.
  - `apps/web/src/routes/empresa/editar.tsx` — deleted, content
    folded into `configuracion.tsx`.
  - `apps/web/src/routes/account.tsx` — drop the `<AppShell>`
    wrapper, add lightweight chrome.
  - `apps/web/src/routes/tenants/members.tsx` — deleted (replaced
    by `/empresa/usuarios`).
  - `apps/web/src/features/tenants/api/hooks.ts` — verify
    `useUpdateTenantMutation` exists; expose `useTenantQuery` for
    the fiscal summary card.
  - Router config — register the new routes, drop the
    `/tenants/$id/members` route.
- Affected tests:
  - `apps/web/tests/unit/components/app-sidebar/` — new
    `app-sidebar.test.tsx`, extend `sidebar-context.test.tsx`
    with the `Empresa` collapse persistence key.
  - `apps/web/tests/unit/routes/empresa/` — three new files.
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — sprint 3.14 follow-up
    section (this sprint).
  - `docs/09-frontend.md` — refresh the route tree to show the
    `/empresa/*` group and the AppShell-vs-IdentityLayout split.
- Affected dependencies: none. shadcn sidebar primitives
  (`SidebarMenuSub`, `SidebarMenuSubButton`) are tailwind-only;
  no new npm package.
- Backend gaps surfaced (documented in the spec, not implemented
  here):
  - Per-user permission overrides — needs a new
    `tenant_member_permissions` table + endpoints + an
    `Actor.permissions` resolver that unions the role catalog
    with the per-user overrides.
  - The `POST /v1/invitations/accept` GUC bug
    (already tracked in [[test-backfill-and-e2e-tooling]] §3.2).
- Out of scope:
  - The wired fiscal-data editor at `/empresa/configuracion` —
    placeholder copy stays until a follow-up sprint.
  - Granular per-user permission grants (the role-driven
    catalog is what the UI surfaces in this change).
  - Audit log of role changes / removals.
  - Re-invite flow when a member was removed and the operator
    wants to invite the same email again.
