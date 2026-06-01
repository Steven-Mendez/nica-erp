## ADDED Requirements

### Requirement: SPA SHALL probe first-login on every authenticated route

The SPA route guard SHALL evaluate `me.display_name === null` on every authenticated route navigation. When the result is `true` and the requested route is not `/welcome`, `/account`, or `/health`, the guard SHALL redirect to `/welcome` before the target route is mounted.

#### Scenario: A freshly registered user requesting `/dashboard` is redirected to `/welcome`

- **GIVEN** a user whose `/v1/me` response has `display_name = null`
- **WHEN** the SPA navigates to `/dashboard`
- **THEN** the guard SHALL redirect to `/welcome` before `/dashboard` is mounted

#### Scenario: A user whose profile is complete is not redirected

- **GIVEN** a user whose `/v1/me` response has `display_name = "Ada Lovelace"`
- **WHEN** the SPA navigates to `/dashboard`
- **THEN** the guard SHALL allow `/dashboard` to mount

#### Scenario: `/account` is exempt from the first-login redirect

- **GIVEN** a user whose `/v1/me` response has `display_name = null`
- **WHEN** the SPA navigates to `/account`
- **THEN** the guard SHALL allow `/account` to mount

### Requirement: `/welcome` SHALL capture `display_name` and `timezone` only

The `/welcome` route SHALL render a form containing exactly two fields: `display_name` (text input, `min(2).max(100)`) and `timezone` (HTML `<select>` populated from `Intl.supportedValuesOf('timeZone')` and pre-selected with `Intl.DateTimeFormat().resolvedOptions().timeZone`). The form MUST NOT include a `locale` field. The route MUST NOT render the AppShell sidebar or top header.

#### Scenario: `locale` is absent from the welcome form

- **WHEN** `/welcome` is rendered in a headless browser
- **THEN** the DOM SHALL contain no element with name, id, or label referencing `locale`, `language`, or `región`

#### Scenario: Timezone is pre-selected from the browser

- **GIVEN** a browser whose `Intl.DateTimeFormat().resolvedOptions().timeZone` returns `Europe/Madrid`
- **WHEN** `/welcome` is mounted
- **THEN** the `timezone` `<select>` SHALL have `value = "Europe/Madrid"` before the user interacts

#### Scenario: `display_name` shorter than 2 characters is rejected client-side

- **WHEN** the user types `"A"` into `display_name` and submits
- **THEN** the form SHALL display a validation error, no network request SHALL be sent, and the user SHALL remain on `/welcome`

### Requirement: `/welcome` submit SHALL call `PATCH /v1/me` and route by guard rules

On valid submit, `/welcome` SHALL call `PATCH /v1/me` with the entered `display_name` and `timezone`. On `204 No Content` success the SPA SHALL invalidate the `/v1/me` query, refetch, and then evaluate the guard's "next step" function against the refreshed `me` and the memberships query. The user SHALL land at the first non-exempt route the guard returns (`/onboarding` if no memberships, `/organizations` otherwise).

#### Scenario: A new user with zero memberships lands on `/onboarding`

- **GIVEN** a user with `display_name = null` and zero memberships
- **WHEN** the user submits `/welcome` successfully
- **THEN** the SPA SHALL navigate to `/onboarding`

#### Scenario: A new user invited to one organization lands on `/organizations`

- **GIVEN** a user with `display_name = null` and one accepted membership
- **WHEN** the user submits `/welcome` successfully
- **THEN** the SPA SHALL navigate to `/organizations`

#### Scenario: `PATCH /v1/me` failure keeps the user on `/welcome`

- **GIVEN** a backend returning `500` for `PATCH /v1/me`
- **WHEN** the user submits `/welcome`
- **THEN** the SPA SHALL display an error toast and the route SHALL remain `/welcome`
