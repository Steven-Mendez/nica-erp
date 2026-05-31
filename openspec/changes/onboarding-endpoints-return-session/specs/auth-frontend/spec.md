## ADDED Requirements

### Requirement: SPA SHALL auto-login after `/confirm` when the password is available

The route `apps/web/src/routes/signup.tsx` SHALL forward the typed password to
`apps/web/src/routes/confirm.tsx` via an in-memory hand-off (a module-scoped
variable, not `history.state`, not `sessionStorage`, not `localStorage`, not
the URL). The value SHALL survive intra-SPA navigation between `/signup` and
`/confirm` but SHALL be lost on a hard browser reload, on tab close, and on
explicit consumption (read-once semantics).

When `confirm.tsx` has a non-empty password in its router state, it SHALL
include the password in the `POST /v1/auth/confirm-signup` request body and,
on a `200` response, SHALL call `storeTokens()` from
`apps/web/src/api/tokenStore.ts` with the returned bundle and invalidate the
`meQueryKey`. The route SHALL then delegate the post-confirm navigation to the
route guard (`apps/web/src/lib/route-guard.ts`), which will resolve to
`/welcome`, `/onboarding`, `/tenants`, or the originally requested route as
already documented.

When `confirm.tsx` does NOT have a password in its router state (e.g. after a
hard reload of the route), it SHALL omit `password` from the request body and,
on a `204` response, SHALL navigate to `/login` exactly as before. The user
SHALL be able to complete signup by logging in manually.

#### Scenario: Invited new user reaches the dashboard without re-typing credentials

- **GIVEN** an empresa owner sent a pending invitation to `nuevo@empresa.com` and the SPA is opened at the invitation link
- **WHEN** the invitee submits the `/signup` form with a valid password, then submits the email code on `/confirm`
- **THEN** the SPA SHALL land on `/dashboard` of the invited empresa
- **AND** no `/login` route SHALL appear in the navigation history between `/confirm` and `/dashboard`
- **AND** no `/tenants` (empresa picker) route SHALL appear in the navigation history between `/confirm` and `/dashboard`

#### Scenario: Hard reload of `/confirm` falls back to `/login`

- **GIVEN** the SPA reached `/confirm?email=nuevo@empresa.com` from `/signup`
- **WHEN** the user reloads the browser tab on `/confirm` and then submits the email code
- **THEN** the SPA SHALL post `confirm-signup` without a `password` field
- **AND** on the `204` response SHALL navigate to `/login`
- **AND** the JS console SHALL NOT show any uncaught error during the reload or the navigation

### Requirement: SPA SHALL auto-store rotated tokens after accepting a first-membership invitation

The route `apps/web/src/routes/invitations/accept.tsx` SHALL post
`POST /v1/invitations/accept` with body `{ token, refresh_token }`, where
`refresh_token` is read from the current `tokenStore`. On the success path it
SHALL:

- When the response body includes a non-null `tokens` field (first-membership
  invitee), call `storeTokens(tokens)` BEFORE invalidating `meQueryKey` and
  `myTenantsKey`, then call `setPickerConfirmed()` and navigate to
  `/dashboard`.
- When the response body has `tokens == null` (veteran user joining a second
  empresa), skip `storeTokens` and otherwise behave identically to the
  current code path: invalidate the two query keys, call
  `setPickerConfirmed()`, navigate to `/dashboard`.

The route SHALL NOT inspect or rely on the prior `custom:active_tenant` claim
of the access token to decide between the two branches; it SHALL switch
purely on the shape of the response body. This keeps the SPA agnostic of the
backend's first-membership decision.

#### Scenario: First-membership invitee lands on the invited dashboard

- **GIVEN** a freshly-signed-up user with no prior memberships who has just accepted an invitation
- **WHEN** `POST /v1/invitations/accept` returns `200` with a non-null `tokens` field and `tenant_id == T`
- **THEN** the SPA SHALL call `storeTokens(tokens)` and navigate to `/dashboard`
- **AND** the sidebar `OrganizationSwitcher` SHALL show empresa `T` as the active empresa
- **AND** subsequent tenant-scoped requests (e.g. `GET /v1/tenants/<T>/members`) SHALL succeed without first hitting `/tenants` for a picker

#### Scenario: Veteran user accepting a second-empresa invitation keeps their current empresa

- **GIVEN** a user already authenticated with `custom:active_tenant == A` who accepts an invitation to empresa `B`
- **WHEN** `POST /v1/invitations/accept` returns `200` with `tenant_id == B` and `tokens == null`
- **THEN** the SPA SHALL NOT call `storeTokens`
- **AND** the SPA SHALL navigate to `/dashboard`
- **AND** the sidebar `OrganizationSwitcher` SHALL still show empresa `A` as the active empresa, with empresa `B` available as a switch target
