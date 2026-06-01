## ADDED Requirements

### Requirement: Frontend slice SHALL be named `organizations`, not `tenants`

The directory `apps/web/src/features/tenants/` SHALL NOT exist after this change. Its contents SHALL live under `apps/web/src/features/organizations/`. TypeScript types exposed by the slice (`Tenant`, `TenantMembership`, `TenantInvitation`) SHALL be renamed to `Organization`, `OrganizationMembership`, `OrganizationInvitation`. The generated client at `apps/web/src/api/schema.d.ts` MAY keep the backend `Tenant*` names; an adapter file in `apps/web/src/features/organizations/api/adapter.ts` SHALL be the single place where the two vocabularies meet.

#### Scenario: No source file imports `features/tenants`

- **WHEN** `rg --type ts --type tsx "@/features/tenants"` is run on `apps/web/src/`
- **THEN** the search SHALL return zero matches

#### Scenario: No source identifier outside the adapter uses `Tenant`

- **WHEN** `rg --type ts --type tsx "\bTenant(?:Membership|Invitation)?\b" apps/web/src/` is run
- **THEN** the only matches SHALL be inside `apps/web/src/features/organizations/api/adapter.ts` and `apps/web/src/api/schema.d.ts`

### Requirement: User-visible copy SHALL use "organización" / "organization"

Every user-visible string in the SPA (page titles, nav labels, buttons, form labels, error messages, toast copy) referring to the tenant aggregate SHALL render the word "organización" (es) or "organization" (en). The word "tenant" / "inquilino" / "empresa" SHALL NOT appear in any user-visible string.

#### Scenario: Sidebar nav item is "Organizaciones"

- **WHEN** the authenticated sidebar is rendered
- **THEN** the nav item that links to `/organizations` SHALL display the text "Organizaciones"

#### Scenario: Title of the picker page is "Tus organizaciones"

- **WHEN** the SPA is mounted at `/organizations`
- **THEN** the page SHALL render an `<h1>` (or equivalent) containing the text "Tus organizaciones"

#### Scenario: No user-visible string contains "tenant"

- **WHEN** the SPA renders any authenticated route
- **THEN** the rendered text content SHALL NOT contain the case-insensitive substring "tenant"

### Requirement: `/organizations` SHALL be the post-login picker

The SPA SHALL navigate authenticated users with `me.active_tenant === null` AND at least one accepted membership to `/organizations`. Authenticated users SHALL ALSO be navigated to `/organizations` after `/welcome` submission and after `/onboarding/new` completion when the wizard's target is "select a different existing organization". The picker SHALL render a card per membership and SHALL include a search input and a "+ Nueva organización" CTA.

#### Scenario: One-membership user passes through the picker each session

- **GIVEN** a user with one accepted membership
- **WHEN** the user logs in
- **THEN** the SPA SHALL navigate to `/organizations` and present the single membership as a card the user must click

#### Scenario: Picker click drives the switch + dashboard navigation

- **GIVEN** the user is on `/organizations` with at least one card
- **WHEN** the user clicks a card
- **THEN** the SPA SHALL call `POST /v1/tenants/{id}/switch`, on success invalidate the auth cache, and navigate to `/dashboard`

### Requirement: `/onboarding` SHALL branch into wizard or invitation acceptance

The `/onboarding` route SHALL render exactly two primary CTAs: "Crear organización" linking to `/onboarding/new`, and "Tengo un código de invitación" linking to `/invitations/accept`. The route MUST NOT call the backend on mount. The route SHALL be shown only to authenticated users whose `memberships.length === 0`; the guard SHALL redirect users with at least one membership away from `/onboarding`.

#### Scenario: Zero-membership user lands on `/onboarding`

- **GIVEN** a user with `memberships.length === 0` and a completed welcome
- **WHEN** the user logs in
- **THEN** the SPA SHALL navigate to `/onboarding` and render both CTAs

#### Scenario: User with memberships SHALL NOT see `/onboarding`

- **GIVEN** a user with `memberships.length >= 1`
- **WHEN** the user navigates to `/onboarding`
- **THEN** the guard SHALL redirect to `/organizations`

### Requirement: Organization creation wizard SHALL be a four-step form

The wizard route (reached at both `/onboarding/new` and `/organizations/new`) SHALL drive the user through four steps with per-step Zod validation:

1. **Identidad** — `name` (Zod `min(2).max(120)`) and `ruc` (Nicaragua RUC schema reused from the existing form).
2. **Régimen fiscal** — `regime` (`general` | `simplified`), `municipality` (combobox), `is_withholder` (boolean).
3. **Autorización DGI** — `authorization_dgi.number` (string) and `authorization_dgi.valid_until` (date).
4. **Dirección fiscal** — `fiscal_address` (textarea) plus a review summary of the previous steps.

On final submit the SPA SHALL POST to `/v1/tenants`, then to `/v1/tenants/{id}/switch`, then navigate to `/dashboard`. The wizard MUST NOT allow advancing to step N+1 while step N has an active Zod error.

#### Scenario: Invalid RUC blocks advance from step 1

- **GIVEN** the wizard is at step 1 with `ruc = "123"`
- **WHEN** the user clicks "Continuar"
- **THEN** the form SHALL display a RUC validation error and SHALL remain on step 1

#### Scenario: Successful completion navigates to `/dashboard`

- **GIVEN** valid input at all four steps and `POST /v1/tenants` returning `201`
- **WHEN** the user submits step 4
- **THEN** the SPA SHALL call `POST /v1/tenants/{id}/switch` and SHALL navigate to `/dashboard`

### Requirement: Members page SHALL expose role change to authorised users

The route `/organizations/$organizationId/members` SHALL render a per-member inline `<select>` for non-owner members when `useHasPermission("members:update-role")` returns `true`. The options SHALL be `viewer`, `salesperson`, `accountant`, `admin` (in that order). On change the SPA SHALL call `PATCH /v1/tenants/{id}/members/{user_id}` with the new role, then invalidate the members query. When the permission check returns `false`, the column SHALL render the static role label only.

#### Scenario: Admin sees the role `<select>`

- **GIVEN** the current actor has the `members:update-role` permission
- **WHEN** the members page lists a non-owner member with role `viewer`
- **THEN** the member's row SHALL contain a `<select>` whose value is `viewer` and whose options include `viewer`, `salesperson`, `accountant`, `admin`

#### Scenario: Viewer SHALL NOT see the role `<select>`

- **GIVEN** the current actor lacks the `members:update-role` permission
- **WHEN** the members page is rendered
- **THEN** the members rows SHALL render the role as static text and no `<select>` SHALL be present

#### Scenario: Owner row is excluded from the role `<select>`

- **GIVEN** the actor has `members:update-role`
- **WHEN** the members page renders a member whose role is `owner`
- **THEN** the row SHALL render the role as static text "owner" and no `<select>` SHALL be present

### Requirement: `/invitations/accept` SHALL accept both hash-fragment and pasted tokens

The route `/invitations/accept` (no `$token` path parameter) SHALL handle three entry modes on mount:

- **Hash-fragment, authenticated**: when `location.hash` starts with `#t=` AND `/v1/me` returns an authenticated user, the SPA SHALL read the token, immediately call `history.replaceState(null, '', location.pathname)`, render a "joining" progress card, and POST `/v1/invitations/accept` with the token in the body.
- **Hash-fragment, unauthenticated**: when `location.hash` starts with `#t=` AND no session is active, the SPA SHALL first call `GET /v1/invitations/{token}/preview` to obtain the invited email, present a signup form pre-filled with that email, and on successful signup + confirm + login proceed with the accept POST.
- **No hash, authenticated**: the SPA SHALL render a paste input where the user submits the token manually. Submit triggers the same accept POST.

On a successful accept the SPA SHALL invalidate the auth cache and navigate to `/organizations`.

#### Scenario: Hash-fragment token is stripped from the URL on mount

- **GIVEN** an authenticated user navigates to `/invitations/accept#t=abc.def.ghi`
- **WHEN** the SPA mounts the route
- **THEN** within one tick of mount, `location.hash` SHALL be empty and `location.pathname` SHALL be `/invitations/accept`

#### Scenario: Manual paste path works without a hash

- **GIVEN** an authenticated user navigates to `/invitations/accept`
- **WHEN** the user pastes a valid token and submits
- **THEN** the SPA SHALL POST `/v1/invitations/accept` with the token and navigate to `/organizations` on success

#### Scenario: Unauthenticated hash-token entry routes through signup

- **GIVEN** an unauthenticated user navigates to `/invitations/accept#t=abc.def.ghi`
- **WHEN** the SPA mounts the route
- **THEN** the SPA SHALL call `GET /v1/invitations/{token}/preview` and present the signup form with the email pre-filled from the preview response

### Requirement: `OrganizationSwitcher` SHALL replace `TenantSwitcher` in the sidebar

The component formerly known as `TenantSwitcher` (sprint-03 dashboard-shell addendum) SHALL be renamed to `OrganizationSwitcher`. Its placement in the `app-sidebar` header is preserved. It SHALL drive in-session organization switching without navigating through `/organizations`.

#### Scenario: Switcher swaps the active organization without leaving the route

- **GIVEN** the user is on `/dashboard` in organization A
- **WHEN** the user opens the `OrganizationSwitcher` and clicks organization B
- **THEN** the SPA SHALL call `POST /v1/tenants/{id}/switch`, invalidate the affected query caches, and remain on `/dashboard` (now reflecting organization B)
