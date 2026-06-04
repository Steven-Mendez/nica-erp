## ADDED Requirements

### Requirement: Token-mint responses MUST NOT include the refresh token in the JSON body

The API SHALL NOT include a `refresh_token` field in the JSON body of `POST /v1/auth/login`, `POST /v1/auth/refresh`, `POST /v1/auth/confirm-signup` (auto-login branch), or `POST /v1/tenants/{id}/switch`. Each such response SHALL contain only `access_token`, `id_token`, and `token_type`. The refresh token SHALL be delivered exclusively via the `Set-Cookie: nica_erp_rt=…; HttpOnly; Secure; SameSite=Lax; Path=/v1; Max-Age=2592000` response header. The response model SHALL NOT define a `refresh_token` field.

#### Scenario: Login response carries the refresh token only in a Set-Cookie header

- **GIVEN** a confirmed user submits valid credentials to `POST /v1/auth/login`
- **WHEN** the API responds with `200 OK`
- **THEN** the response body SHALL contain `access_token`, `id_token`,
  and `token_type`, and SHALL NOT contain a `refresh_token` key
- **AND** the response SHALL include a `Set-Cookie` header whose name
  is `nica_erp_rt`, value is a JWT with `typ:"refresh"`, and
  attributes are `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/v1`,
  `Max-Age=2592000`

#### Scenario: Refresh response rotates via cookie only

- **GIVEN** a logged-in SPA holding a valid refresh cookie
- **WHEN** the SPA calls `POST /v1/auth/refresh` with an empty body
  and `credentials: "include"`
- **THEN** the API SHALL accept the cookie as the refresh-token source
- **AND** the response body SHALL contain `access_token`, `id_token`,
  and `token_type`, and SHALL NOT contain `refresh_token`
- **AND** the response SHALL include an updated `Set-Cookie:
  nica_erp_rt=…` header carrying the freshly rotated refresh token

#### Scenario: Tenant switch response carries no refresh token in the body

- **GIVEN** a logged-in user holding a valid access token and a valid
  refresh cookie for tenant A
- **WHEN** the SPA calls `POST /v1/tenants/B/switch` with an empty
  body and `credentials: "include"`
- **THEN** the API SHALL accept the cookie as the refresh-token source
- **AND** the JSON body SHALL contain `access_token`, `id_token`, and
  `token_type` (no `refresh_token`)
- **AND** the response SHALL include a rotated `Set-Cookie:
  nica_erp_rt=…` header

### Requirement: The SPA MUST NOT persist the refresh token in browser storage

The SPA SHALL NOT write the refresh token to `localStorage`,
`sessionStorage`, IndexedDB, or any storage surface readable from
JavaScript. The cookie set by the API is the only persistent carrier.
The SPA's `tokenStore` SHALL only retain access and id tokens, both
in module-scoped JavaScript memory.

#### Scenario: sessionStorage holds no refresh token after login

- **GIVEN** a confirmed user submits `POST /v1/auth/login` via the SPA
- **WHEN** the login round-trip completes successfully
- **THEN** `window.sessionStorage.getItem('nica-erp:refresh-token')`
  SHALL return `null`
- **AND** `Object.keys(window.sessionStorage)` SHALL NOT contain any
  key whose value is a JWT with `typ:"refresh"`

#### Scenario: sessionStorage holds no refresh token after a successful refresh

- **GIVEN** a logged-in SPA whose access token has expired
- **WHEN** the interceptor's `tryRefresh` round-trip completes
  successfully
- **THEN** `window.sessionStorage.getItem('nica-erp:refresh-token')`
  SHALL return `null`
- **AND** the only auth-related JS state SHALL be the in-memory access
  and id tokens

#### Scenario: sessionStorage holds no refresh token after a tenant switch

- **GIVEN** a logged-in SPA on tenant A
- **WHEN** the user switches to tenant B and the round-trip completes
- **THEN** `window.sessionStorage.getItem('nica-erp:refresh-token')`
  SHALL return `null`

### Requirement: The SPA's boot refresh MUST run unconditionally and rely on the cookie

On every fresh tab load the SPA SHALL issue exactly one
`POST /v1/auth/refresh` with an empty body and
`credentials: "include"`, regardless of any in-memory or storage
state. If the API returns `401 auth.invalid_credentials` the SPA
SHALL render the unauthenticated shell (e.g., redirect to `/login`).
The SPA SHALL NOT branch boot behavior on the presence of any
JavaScript-readable refresh token.

#### Scenario: Boot refresh succeeds via cookie after reload

- **GIVEN** a user has logged in (so `nica_erp_rt` is set as a cookie)
- **AND** the user reloads the SPA tab so JS state is wiped
- **WHEN** `bootRefresh` runs on mount
- **THEN** it SHALL POST `/v1/auth/refresh` with empty body +
  `credentials: "include"`
- **AND** on `200 OK`, the SPA SHALL hydrate the in-memory access
  token and proceed to the authenticated shell

#### Scenario: Boot refresh fails gracefully when no cookie is set

- **GIVEN** a tab with no `nica_erp_rt` cookie (first visit or post-
  logout)
- **WHEN** `bootRefresh` runs on mount
- **THEN** the API SHALL return `401 auth.invalid_credentials`
- **AND** the SPA SHALL route to the unauthenticated shell without
  surfacing an error toast
