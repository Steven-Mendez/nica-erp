## ADDED Requirements

### Requirement: Refresh tokens have a server-side jti ledger and are revocable

The local identity provider SHALL persist every issued refresh token's
`jti` in a database row at mint time, and SHALL consult that row on
every subsequent refresh-token verification. `POST /v1/auth/logout`
SHALL revoke the supplied refresh token's row. A revoked jti SHALL be
treated as if the token were forged.

#### Scenario: Logout revokes the refresh token and a subsequent refresh fails

- **GIVEN** an authenticated session with refresh token `RT_1`
- **AND** `RT_1`'s jti is present in `auth_local_refresh_tokens` with
  `revoked_at IS NULL`
- **WHEN** the SPA calls `POST /v1/auth/logout`
- **THEN** the API SHALL set `revoked_at = now()` for `RT_1.jti` and
  return `204 No Content`
- **AND** a subsequent `POST /v1/auth/refresh` with `RT_1` SHALL return
  `401 auth.invalid_credentials`

#### Scenario: Logout is idempotent for missing or already-revoked tokens

- **GIVEN** a request to `POST /v1/auth/logout` for a refresh token
  whose jti is already revoked OR whose jti was never inserted
- **WHEN** the endpoint runs
- **THEN** it SHALL return `204 No Content`
- **AND** SHALL NOT leak any information distinguishing the cases

### Requirement: The bearer-auth verifier asserts the access token type and audience

The bearer-auth verifier SHALL reject any JWT whose `typ` claim is not `"access"` or whose `aud` claim does not match the configured access-token audience, on every route except `/v1/auth/refresh`. The rejection SHALL produce `401 auth.invalid_credentials` with no body distinction.

#### Scenario: Refresh token rejected as access token

- **GIVEN** the SPA holds a refresh token `RT` with `typ:"refresh"` and
  `aud:"nica-erp-local-refresh"`
- **WHEN** the SPA sends `GET /v1/me` with
  `Authorization: Bearer <RT>`
- **THEN** the API SHALL return `401 auth.invalid_credentials`
- **AND** SHALL NOT process the request as if it were an access token

#### Scenario: Access token with wrong audience rejected

- **GIVEN** a JWT carrying `typ:"access"` but `aud:"nica-erp-local-refresh"`
- **WHEN** the JWT is sent as `Authorization: Bearer` to `/v1/tenants`
- **THEN** the API SHALL return `401 auth.invalid_credentials`

### Requirement: Refresh tokens are transported via httpOnly cookies, not body or storage

The API SHALL set the refresh token via `Set-Cookie: nica_erp_rt=…;
HttpOnly; Secure; SameSite=Lax; Path=/v1/auth/refresh;
Max-Age=2592000` on every endpoint that mints one (`/v1/auth/login`,
`/v1/auth/confirm-signup` auto-login, `/v1/auth/refresh`,
`/v1/tenants/{id}/switch`). The response JSON SHALL NOT include the
refresh token. The SPA SHALL NOT persist any refresh token in
`localStorage` or `sessionStorage`.

#### Scenario: Login response carries the refresh token only in a Set-Cookie header

- **GIVEN** a successful `POST /v1/auth/login`
- **WHEN** the API returns the response
- **THEN** the response SHALL include a `Set-Cookie: nica_erp_rt=…`
  header with the documented flags
- **AND** the response JSON SHALL NOT include a `refresh_token` field

#### Scenario: SPA does not persist the refresh token

- **GIVEN** a successful sign-in flow
- **WHEN** the SPA mounts the authenticated dashboard
- **THEN** `Object.keys(sessionStorage)` SHALL NOT include
  `nica-erp:refresh-token`
- **AND** `Object.keys(localStorage)` SHALL NOT include
  `nica-erp:refresh-token`
- **AND** the SPA's `tryRefresh` SHALL call `/v1/auth/refresh` with
  `credentials:'include'` so the browser attaches the cookie
