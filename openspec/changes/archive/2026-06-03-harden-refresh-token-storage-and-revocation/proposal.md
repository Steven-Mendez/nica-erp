## Why

Three audit findings (F-005, F-011, F-016) chain into a single critical
risk: **one XSS = 30-day non-revocable account takeover**.

1. **F-005** — the refresh token JWT is stored in `sessionStorage`
   (`nica-erp:refresh-token`, 276-char `eyJ…` string). Verified live:
   `sessionStorage.getItem('nica-erp:refresh-token')` returns it.
2. **F-011** — the API's JWT verifier does not check the `typ` claim.
   The refresh token (claim `typ:"refresh"`) is accepted by every
   authenticated endpoint, including `POST /v1/tenants`. The audit
   created `Empresa Hackeada Con Refresh` using only the refresh JWT.
3. **F-016** — `POST /v1/auth/logout` returns 204 but does not
   revoke. The same access token continues to return 200 on
   `/v1/me`; the same refresh token continues to mint new
   access+refresh pairs on `/v1/auth/refresh`. The `local.py` source
   comment admits "Refresh tokens are stateless (MVP); `global_signout`
   is a no-op for that reason."

These three together mean: an attacker who lands ONE XSS payload reads
the refresh token from `sessionStorage`, hits any API endpoint with it
as `Authorization: Bearer …` (no need to call `/refresh` first), AND
retains access for 30 days even if the user notices and clicks
"Cerrar sesión".

This change closes all three holes together: move the refresh token to
an httpOnly cookie, reject the refresh token on non-refresh endpoints,
and add a server-side refresh-token revocation list.

## What Changes

### Backend — refresh-token revocation table

- New table `auth_local_refresh_tokens (jti UUID PRIMARY KEY, user_id UUID,
  issued_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ NULL,
  user_agent TEXT NULL, ip TEXT NULL)`.
- Local IdP `_make_refresh_token` SHALL INSERT a row keyed by the
  token's `jti` (must be added to the claim if absent) before returning
  the JWT.
- `POST /v1/auth/logout` SHALL set `revoked_at = now()` for the supplied
  refresh token's `jti`. If the row is missing OR already revoked, the
  endpoint SHALL still return 204 (idempotent, no info leak).
- `POST /v1/auth/refresh` SHALL reject any refresh token whose `jti` is
  missing from the table OR has a non-null `revoked_at` — return 401
  `auth.invalid_credentials` (no body distinction).
- A daily housekeeping migration removes rows whose `issued_at` is
  beyond the refresh-token TTL (30 days).

### Backend — JWT verifier asserts `typ:"access"`

- Bearer-auth middleware (whatever guards routes under
  `/v1/me /v1/tenants/* /v1/invitations/*`) SHALL parse the JWT
  payload's `typ` claim and reject tokens whose `typ != "access"` with
  401 `auth.invalid_credentials`. The only exception is
  `POST /v1/auth/refresh`, which accepts (and requires)
  `typ:"refresh"`.
- Access-token mint paths (`login`, `confirm-signup` auto-login,
  `refresh`, `switch`) SHALL set `typ:"access"` on the access claim
  (today the access claim has no `typ` at all — add it).

### Backend — distinct audience for refresh tokens

- Defense in depth: mint refresh tokens with `aud:"nica-erp-local-refresh"`
  and access tokens with `aud:"nica-erp-local-api"`. The `/v1/auth/refresh`
  endpoint verifies the refresh audience; every other route verifies the
  access audience. The current single `aud:"nica-erp-local"` SHALL be
  retired after a single deploy cycle (a one-cycle compatibility
  acceptance is OUT of scope for local — drop it immediately).

### Frontend — refresh token in httpOnly cookie

- `apps/api/src/contexts/identity/adapters/inbound/http/router.py`:
  - `/v1/auth/login`, `/v1/auth/confirm-signup` (auto-login branch),
    `/v1/auth/refresh`, `/v1/tenants/{id}/switch` SHALL set the
    refresh token via `Set-Cookie: nica_erp_rt=<jwt>; HttpOnly; Secure;
    SameSite=Lax; Path=/v1/auth/refresh; Max-Age=<30 days>`. The
    response JSON SHALL stop emitting `refresh_token` for SPA callers
    (only the access token remains in-body).
  - `/v1/auth/logout` SHALL clear the cookie via
    `Set-Cookie: nica_erp_rt=; Max-Age=0; Path=/v1/auth/refresh`.
- `apps/web/src/api/`:
  - The in-memory store SHALL stop touching `sessionStorage` for the
    refresh token. The key `nica-erp:refresh-token` SHALL be deleted at
    startup if found (defensive cleanup for upgraders).
  - `tryRefresh` SHALL call `/v1/auth/refresh` with
    `credentials:'include'` and an empty body. The browser attaches
    the httpOnly cookie automatically.
  - The `switch` mutation SHALL also use `credentials:'include'` and
    stop passing `refresh_token` in the body; the server reads it from
    the cookie.

### Tests

- Backend unit: refresh-token mint inserts a row, logout revokes,
  refresh on revoked jti returns 401.
- Backend unit: a refresh-typ token sent as `Authorization: Bearer` to
  `/v1/me` returns 401.
- Backend integration: full login → /me → logout → /refresh (expect
  401) → /me with stale AT (still 401 due to revoked refresh OR
  natural expiry).
- Frontend unit: the SPA does not write to `sessionStorage` for the
  refresh token after sign-in; document.cookie also remains empty
  (cookie is httpOnly, invisible to JS).

## Non-goals

- Switching to opaque (DB-id) refresh tokens — keep the HS256 JWT
  format, add the jti-table as the source of truth.
- Cognito parity (this change only addresses `APP_ENV=local`'s
  local IdP; Cognito's refresh handling is separate).
- Revoking *access* tokens before natural expiry. Once the refresh is
  revoked, the SPA cannot refresh, and the AT dies of natural causes
  (~1 h). Hard AT revocation is out of scope.
