## ADDED Requirements

### Requirement: Post-login flow lands on the empresa picker on every browser session

After authentication, the SPA SHALL render the empresa picker at
`/tenants` before reaching `/dashboard` whenever the session-scoped
flag `sessionStorage["nica-erp:picker-confirmed"]` is unset, **even
if the JWT already carries `custom:active_tenant`**.

The flag SHALL be cleared by `useLogoutMutation`'s `onSuccess`
handler and by the `Cambiar empresa` entry on the sidebar's
`TenantSwitcher`. The flag SHALL be set when the operator confirms
an empresa from the picker (clicking a card and the switch mutation
resolving), and when the operator successfully creates a new empresa
via `/tenants/new` (the auto-switch already runs in that flow).

The flag MUST live in `sessionStorage` so it clears automatically
when the tab closes. It MUST NOT be written to `localStorage` or any
cookie.

The probe MUST be bypassed for routes already listed in
`TENANT_EXEMPT` (`/welcome`, `/onboarding`, `/tenants`,
`/tenants/new`, `/account`, `/health`).

#### Scenario: Returning operator with one empresa lands on the picker

- **GIVEN** the operator's JWT carries
  `custom:active_tenant = "<tenant_id>"`
- **AND** `sessionStorage["nica-erp:picker-confirmed"]` is unset
- **WHEN** the SPA boots and `beforeLoad` runs for `/dashboard`
- **THEN** the route guard redirects to `/tenants`

#### Scenario: After confirming a card, the dashboard is reachable

- **GIVEN** the operator is on `/tenants` and clicks an empresa card
- **WHEN** `useSwitchTenantMutation` resolves
- **THEN** `sessionStorage["nica-erp:picker-confirmed"]` is set to
  `"1"` and the SPA navigates to `/dashboard`

#### Scenario: Logout clears the flag

- **GIVEN** the operator has confirmed an empresa and the flag is
  set
- **WHEN** the operator triggers logout
- **THEN** `sessionStorage["nica-erp:picker-confirmed"]` is removed
  and the next sign-in re-shows the picker

### Requirement: Empresa picker matches the Supabase reference layout

The route `/tenants` SHALL render a Supabase-style picker:

- Page title `Tus empresas` via `useDocumentTitle("Tus empresas")`.
- A search `<Input>` with Spanish placeholder
  `Buscar una empresa…` that filters the visible cards by `name`
  using a case-insensitive substring match.
- A primary `+ Nueva empresa` `<Button>` linking to `/tenants/new`
  rendered on the right side of the page header.
- A responsive grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`)
  of `<Card>` tiles, one per accepted membership.
- Each card MUST show:
  - A two-letter initials avatar derived from the empresa `name`
    (first character of the first two whitespace-split tokens,
    uppercased).
  - The empresa `name` as the card's primary text.
  - The operator's role on the card (Spanish label, e.g.
    `Propietario`, `Administrador`, `Contador`).
  - A subtitle line showing the pending invitation count for the
    operator's role, e.g. `2 invitaciones pendientes`, sourced
    from `GET /v1/tenants/{id}/invitations` filtered to
    `status === "pending"`. When the count is zero, the line MUST
    be omitted (not rendered as `0 invitaciones pendientes`).
- The card's entire surface MUST be clickable (`role="button"`)
  and MUST fire `useSwitchTenantMutation` on activation.

The single-card variant (operator belongs to exactly one empresa)
MUST render the same card layout. Auto-skip is **forbidden**.

The empty-state MUST reuse the existing `<Alert>` + link to
`/tenants/new` ("Aún no tienes empresas — Crea una empresa para
empezar a facturar.").

#### Scenario: Search filters the cards by name

- **GIVEN** the operator belongs to three empresas
  (`Acme`, `Bagel Shop`, `Acme Coffee`)
- **WHEN** the operator types `acme` in the search input
- **THEN** exactly two cards render (`Acme`, `Acme Coffee`)

#### Scenario: Clicking a card switches and sets the picker flag

- **GIVEN** the operator is on `/tenants` and the picker-confirmed
  flag is unset
- **WHEN** the operator clicks the `Acme` card
- **THEN** `useSwitchTenantMutation` is called with the `Acme`
  empresa id, `sessionStorage["nica-erp:picker-confirmed"]` is set
  to `"1"`, and the SPA navigates to `/dashboard`

#### Scenario: Empty state with zero memberships

- **GIVEN** the operator has zero accepted memberships
- **WHEN** the picker renders
- **THEN** the empty-state `<Alert>` is visible with the
  `Crear empresa` link to `/tenants/new`

## MODIFIED Requirements

### Requirement: Sidebar `TenantSwitcher` exposes a persistent "Cambiar empresa" entry

The sidebar header's `TenantSwitcher` popover SHALL list a
`Cambiar empresa` row at the bottom, separated from the empresa
list by a `<Separator />`. The row MUST be rendered for every
authenticated operator, including those who belong to a single
empresa.

Activating the row SHALL:

1. Remove `sessionStorage["nica-erp:picker-confirmed"]`.
2. Navigate to `/tenants` via the router.

The collapsed sidebar variant MUST keep the entry visible through
the chip's hover popover.

#### Scenario: Cambiar empresa link returns to the picker

- **GIVEN** the operator is on `/dashboard` and the picker flag is
  set
- **WHEN** the operator opens the sidebar's `TenantSwitcher` and
  activates `Cambiar empresa`
- **THEN** the flag is removed and the SPA navigates to `/tenants`

#### Scenario: Single-empresa operator still sees the entry

- **GIVEN** the operator belongs to exactly one empresa
- **WHEN** the sidebar's `TenantSwitcher` popover opens
- **THEN** the popover lists the one empresa AND the
  `Cambiar empresa` row at the bottom
