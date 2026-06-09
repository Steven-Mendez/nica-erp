# empresa-section Specification

## Purpose
TBD - created by archiving change restructure-sidebar-empresa-and-account. Update Purpose after archive.
## Requirements
### Requirement: Nested route group `/empresa/*` operates on the active empresa

The SPA SHALL expose a nested route group under `/empresa/*` that
operates on the operator's **active** empresa derived from
`me.active_tenant`. The group MUST NOT use a `$tenantId` URL
segment.

The group contains three routes:

- `/empresa` (Vista general) — fiscal summary of the active
  empresa.
- `/empresa/usuarios` — member list + pending invitations + invite
  dialog.
- `/empresa/configuracion` — fiscal-data editor (placeholder
  "Próximamente" copy until the wired editor lands).

Every page in the group MUST:

- Render inside `<AppShell>` so the sidebar (and its `Empresa`
  multi-level entry) stays visible.
- Resolve the active empresa via `useMeQuery()` →
  `me.data?.active_tenant`. When `active_tenant === null`, the
  page MUST redirect to `/tenants` (the picker) — never render an
  empty state.
- Call its data hooks with `me.active_tenant` (not a URL `$id`).

#### Scenario: Empresa group derives the tenant from `me.active_tenant`

- **GIVEN** the operator is authenticated with
  `me.active_tenant = "<uuid-A>"`
- **WHEN** the operator navigates to `/empresa/usuarios`
- **THEN** the page calls `useMembersQuery("<uuid-A>")` and
  renders the members of empresa A

#### Scenario: Empresa group redirects to picker when active is null

- **GIVEN** `me.active_tenant === null`
- **WHEN** the operator navigates to `/empresa/usuarios`
- **THEN** the route guard / route loader redirects to `/tenants`

### Requirement: `/empresa` renders the fiscal summary

The route `/empresa` SHALL render a `<Card>` summarising the active
empresa's fiscal data, reusing the four-section Revisión card
layout established by sprint 3.10
(`polish-tenants-new-form-final`):

- Identidad — `name`, `ruc` (or `Pendiente de capturar` placeholder
  when null).
- Régimen fiscal — `regime` (Spanish label), `municipality`,
  `is_withholder` rendered as a `<Badge>`.
- Autorización DGI — `number`, `valid_from → valid_to` in
  `dd MMM yyyy` Spanish format (or `Pendiente` when the block is
  null).
- Dirección — `fiscal_address` (or `Pendiente`).

When `ruc === null || fiscal_address === null`, the page MUST also
render the soft-creation `<Alert>` banner introduced by sprint
3.11 with a link to `/empresa/configuracion`.

#### Scenario: Vista general renders Revisión card for a populated empresa

- **WHEN** the operator navigates to `/empresa` with a fully
  populated active empresa
- **THEN** all four sections render with their values; no
  `Pendiente` placeholders; no soft-creation banner

#### Scenario: Vista general renders Pendiente placeholders for a soft-created empresa

- **WHEN** the operator navigates to `/empresa` with
  `ruc === null && fiscal_address === null`
- **THEN** the Identidad RUC value reads `Pendiente de capturar`,
  the Dirección value reads `Pendiente`, and the soft-creation
  banner is visible pointing to `/empresa/configuracion`

### Requirement: `/empresa/usuarios` exposes members + invitations + invite flow

The route `/empresa/usuarios` SHALL render two stacked `<Card>`s:

- **Miembros** — table from
  `GET /v1/tenants/{active_tenant_id}/members`. Columns:
  Nombre / Email / Rol / Acciones. The owner row's role cell is
  static text (the single-owner invariant from sprint 03 forbids
  changing or removing the owner). Non-owner rows render:
  - Inline role `<Select>` (options: `viewer`, `salesperson`,
    `accountant`, `admin`) when
    `useHasPermission("members:update-role")` returns `true`;
    otherwise static text.
  - `Remover` button when
    `useHasPermission("members:remove")` returns `true`;
    otherwise hidden.
- **Invitaciones pendientes** — table from
  `GET /v1/tenants/{active_tenant_id}/invitations` filtered to
  `status === "pending"`. Columns: Email / Rol propuesto / Enviada
  / Acciones. The Acciones column shows a `Cancelar` button when
  `useHasPermission("members:invite")` returns `true`.

The page header MUST render a primary `+ Invitar` button when
`useHasPermission("members:invite")` returns `true`. The button
opens a `<Dialog>` containing the existing `inviteMemberSchema`
form (email + proposed_role Select). On success, the dialog
closes and both tables invalidate.

#### Scenario: Owner-role row is never editable

- **GIVEN** the operator views `/empresa/usuarios`
- **WHEN** the members table renders
- **THEN** the row whose role is `owner` shows the role as static
  text and renders no inline `<Select>` and no `Remover` button,
  regardless of the operator's permissions

#### Scenario: Viewer sees only the lists, no affordances

- **GIVEN** the operator's role is `viewer` (no `members:invite`,
  no `members:update-role`, no `members:remove` — and no
  `members:read` either)
- **WHEN** the operator navigates to `/empresa/usuarios`
- **THEN** the page redirects to `/dashboard` (or surfaces a 403
  empty state per ADR-0022) since `members:read` is missing

#### Scenario: Accountant sees the lists, no write affordances

- **GIVEN** the operator's role is `accountant` (has
  `members:read` only)
- **WHEN** the operator navigates to `/empresa/usuarios`
- **THEN** both tables render with no inline `<Select>`, no
  `Remover` button, no `Cancelar` button, and no `+ Invitar`
  button

### Requirement: `/empresa/configuracion` is the canonical fiscal-data editor route

The route `/empresa/configuracion` SHALL be the canonical URL for
the fiscal-data editor. The existing placeholder at
`apps/web/src/routes/empresa/editar.tsx` SHALL be removed and its
copy folded into the new route.

Until the wired editor lands, the page MUST render a `<Card>` with
title `Configuración de la empresa` and the body copy
`Próximamente — esta pantalla permitirá editar los datos fiscales
de tu empresa.`

The soft-creation banner from `/empresa` (when fields are missing)
MUST link to `/empresa/configuracion`, NOT the old
`/empresa/editar`.

#### Scenario: Soft-creation banner links to the canonical config route

- **GIVEN** the operator sees the soft-creation banner on
  `/dashboard` or `/empresa`
- **WHEN** the operator clicks `Completar ahora`
- **THEN** the SPA navigates to `/empresa/configuracion`
