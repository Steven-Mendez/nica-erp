## 1. Sprint doc

- [x] 1.1 Append "Sprint follow-up — Empresa section + account scope split (sprint 3.14, 2026-05-28)" to `docs/sprints/03-tenants-and-rls.md` after the existing 3.13 follow-up. Cover motivation (operator report — empresa management surface unreachable from the sidebar, account scope confused with empresa scope), scope (sidebar primitives, new route group, account chrome split), non-goals (no wired fiscal editor, no per-user permission overrides, no audit log).

## 2. Sidebar multi-level primitives

- [x] 2.1 In `apps/web/src/components/app-sidebar/sidebar.tsx`, add `SidebarMenuSub` (the `<ul>` container) and `SidebarMenuSubButton` (the child row with an active-state left rule). Mirror the upstream shadcn API surface so future shadcn updates land cleanly.
- [x] 2.2 Extend `SidebarProvider` / `useSidebar` (or add a sibling hook `useSidebarSection(key: string, defaultOpen?: boolean)`) so each multi-level section can persist its open/closed state under `localStorage["nica-erp:sidebar-<key>-open"]` independent of the global expanded/collapsed state.
- [x] 2.3 Implement the collapsed-sidebar variant: when the global state is `collapsed`, clicking the parent row opens a Tooltip-anchored popover listing the children instead of expanding inline. Reuse `<Popover>` from `@/components/ui/popover` (already installed by sprint 3.9).

## 3. Sidebar nav restructure

- [x] 3.1 In `apps/web/src/components/app-sidebar/app-sidebar.tsx`, replace the `Tenants` flat NAV_ITEMS entry with an `Empresa` parent row using the new `SidebarMenuSub`. Children: `Vista general → /empresa`, `Usuarios → /empresa/usuarios`, `Configuración → /empresa/configuracion`. Parent icon: `Building2`.
- [x] 3.2 Active-state matching: the parent row is active when `pathname === "/empresa" || pathname.startsWith("/empresa/")`. The child row is active when its `to` is an exact prefix of the pathname.
- [x] 3.3 In `apps/web/src/components/app-sidebar/nav-user.tsx`, append a `Mi cuenta` row to the user menu (above the existing `Cerrar sesión`). Activating it calls `navigate({ to: "/account" })`.

## 4. New empresa-scoped routes

- [x] 4.1 Create `apps/web/src/routes/empresa/index.tsx` (Vista general). Imports: `useMeQuery`, `useTenantQuery`. Renders the four-section Revisión card (Identidad / Régimen fiscal / Autorización DGI / Dirección) re-using the layout from sprint 3.10. Renders the soft-creation `<Alert>` from sprint 3.11 when `tenant.ruc === null || tenant.fiscal_address === null`, linking to `/empresa/configuracion`. When `me.active_tenant === null`, redirect to `/tenants`.
- [x] 4.2 Create `apps/web/src/routes/empresa/usuarios.tsx`. Two stacked `<Card>`s as specified in `specs/empresa-section/spec.md`:
  - **Miembros** card pulls from `useMembersQuery(me.active_tenant)`; columns Nombre / Email / Rol / Acciones. Owner row's role is static; non-owner rows have the role `<Select>` (gated `members:update-role`) + `Remover` button (gated `members:remove`).
  - **Invitaciones pendientes** card pulls from `useInvitationsQuery(me.active_tenant)` filtered to `status === "pending"`. Cancel button gated `members:invite`.
  - Page header `+ Invitar` button gated `members:invite` opens a `<Dialog>` with the existing `inviteMemberSchema` form. On success, the dialog closes; both queries invalidate.
- [x] 4.3 Create `apps/web/src/routes/empresa/configuracion.tsx`. Render a `<Card>` with title `Configuración de la empresa` and body `Próximamente — esta pantalla permitirá editar los datos fiscales de tu empresa.` Wire `useDocumentTitle("Configuración de la empresa")`.
- [x] 4.4 Delete `apps/web/src/routes/empresa/editar.tsx`. Any link pointing at `/empresa/editar` SHALL be updated to `/empresa/configuracion` (including the soft-creation banner on `/dashboard` and `/empresa`).
- [x] 4.5 Delete `apps/web/src/routes/tenants/members.tsx`. Update the router config to drop the `/tenants/$id/members` registration.

## 5. AppShell + IdentityLayout split

- [x] 5.1 Create `apps/web/src/components/identity-layout/identity-layout.tsx`. Thin chrome with a top bar containing the `TenantSwitcher` chip on the right and a `← Volver` link on the left. The Volver link reads `sessionStorage["nica-erp:last-app-route"]` (default `/dashboard`) and navigates to it.
- [x] 5.2 In `apps/web/src/components/app-shell/app-shell.tsx`, write the current pathname to `sessionStorage["nica-erp:last-app-route"]` on every mount (`useEffect` with `routerState.pathname` as the dep).
- [x] 5.3 In `apps/web/src/routes/account.tsx`, replace the `<AppShell>` wrapper with `<IdentityLayout>`. The three identity cards stay structurally identical; only the chrome changes.
- [x] 5.4 Verify `apps/web/src/routes/tenants/index.tsx` and `apps/web/src/routes/tenants/new.tsx` continue to render without `<AppShell>` so the picker + create flow stay outside the dashboard chrome (matches [[force-tenant-picker-and-back-link]] §design.md).

## 6. Hooks

- [x] 6.1 In `apps/web/src/features/tenants/api/hooks.ts`, add `useUpdateTenantMutation(tenantId: string)` calling `PATCH /v1/tenants/{tenantId}` and invalidating `useTenantQuery(tenantId)` on success. The mutation is wired even though the editor is not — keeps `Empresa → Configuración` ready for the follow-up sprint.
- [x] 6.2 Verify the existing `useMembersQuery`, `useInvitationsQuery`, `useInviteMemberMutation`, `useCancelInvitationMutation`, `useUpdateMemberRoleMutation`, `useRemoveMemberMutation` accept a `tenantId` argument and that their `queryKey` includes it (so switching empresas naturally invalidates the cache).

## 7. Tests

- [x] 7.1 New file `apps/web/tests/unit/components/app-sidebar/app-sidebar.test.tsx`:
  - (a) Renders the six top-level entries (Resumen, Ventas, Inventario, Reportes, Empresa, Settings).
  - (b) No `Tenants` entry present.
  - (c) `Empresa` parent renders with chevron toggle; clicking it flips `localStorage["nica-erp:sidebar-empresa-open"]`.
  - (d) When pathname is `/empresa/usuarios`, both the `Empresa` parent and the `Usuarios` child show the active state.
- [x] 7.2 Extend `apps/web/tests/unit/components/app-sidebar/sidebar-context.test.tsx` (or add `use-sidebar-section.test.tsx`) to cover the per-section persistence key.
- [x] 7.3 New file `apps/web/tests/unit/routes/empresa/index.test.tsx`:
  - (a) Mocked `useMeQuery` + `useTenantQuery` with a populated tenant render the four-section Revisión card; no soft-creation banner.
  - (b) Mocked `useTenantQuery` with `ruc === null && fiscal_address === null` renders Pendiente placeholders + the soft-creation banner.
- [x] 7.4 New file `apps/web/tests/unit/routes/empresa/usuarios.test.tsx`:
  - (a) Mocked `useHasPermission("members:update-role") === true` renders inline role `<Select>` for non-owner rows; `false` renders static text.
  - (b) Owner row never renders the inline `<Select>` or `Remover` button.
  - (c) `+ Invitar` button is hidden when `members:invite` is `false`; visible and clickable when `true`. Clicking opens the dialog.
  - (d) Mocked `useInvitationsQuery` returning a pending row renders the row with a `Cancelar` button.
- [x] 7.5 New file `apps/web/tests/unit/routes/account.test.tsx`:
  - (a) Renders the three identity cards.
  - (b) The DOM contains no `[data-sidebar]` element (asserts AppShell is gone).
  - (c) The `← Volver` link reads `sessionStorage["nica-erp:last-app-route"]`. When unset, the link target is `/dashboard`.
- [x] 7.6 Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`. All three must pass.

## 8. Smoke

- [ ] 8.1 In the dev server, log in. Confirm the sidebar shows `Empresa` (not `Tenants`) and that expanding it reveals Vista general / Usuarios / Configuración.
- [ ] 8.2 Click each sub-item. Verify the page renders inside the AppShell with the parent + child rows highlighted.
- [ ] 8.3 On `/empresa/usuarios`, verify the members table renders the owner row without affordances, and (as owner) the invite dialog works end-to-end (POST 201, dialog closes, both queries reload).
- [ ] 8.4 From `/dashboard`, open the user menu in the sidebar footer and click `Mi cuenta`. Verify the SPA navigates to `/account` and the AppShell chrome is replaced by `IdentityLayout` (no sidebar, only a top bar with `← Volver` and the empresa chip).
- [ ] 8.5 From `/account`, click `← Volver` and verify the SPA returns to `/dashboard` (or wherever the operator was last).

## 9. Backend gap docs

- [x] 9.1 Append a "Backend gap — per-user permission overrides" note to `docs/sprints/03-tenants-and-rls.md` referencing the spec under `specs/tenants-http/spec.md`. The note SHALL say the gap is **specified but not implemented** by this sprint, and SHALL link to the spec.
- [x] 9.2 Cross-reference the `POST /v1/invitations/accept` GUC bug from the same sprint doc section (already tracked under `test-backfill-and-e2e-tooling` §3.2).

## 10. Validation

- [x] 10.1 `openspec validate restructure-sidebar-empresa-and-account` exits 0.
- [ ] 10.2 `openspec list` reports the change as Active with 100% tasks complete (when this work lands).
