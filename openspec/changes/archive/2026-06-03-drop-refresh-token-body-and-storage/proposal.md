## Why

The 2026-06-03 refresh-token hardening shipped the `nica_erp_rt` HttpOnly
cookie but **kept** `refresh_token` in the JSON body and on
`sessionStorage` as a "transition" (archived tasks 5.2 / 6.2 / 7.6). The
recent audit (F-011) confirmed the SPA still persists the JWT in
`sessionStorage['nica-erp:refresh-token']`, so one XSS = 30-day
non-revocable session — exactly the risk the cookie work was supposed
to mitigate. The existing `auth-refresh-token-lifecycle` spec already
mandates the final state ("response JSON SHALL NOT include the refresh
token", "SPA SHALL NOT persist any refresh token"), but lacks
scenarios that would have caught the regression.

## What Changes

- API: `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/confirm-signup`
  (auto-login branch), `/v1/tenants/{id}/switch` SHALL stop including
  `refresh_token` in the response body. The `nica_erp_rt` HttpOnly
  cookie remains the sole carrier. **BREAKING** for any client reading
  `response.refresh_token` (only the SPA today; no external API
  consumers per ADR-0014 monorepo posture).
- SPA `apps/web/src/api/tokenStore.ts`: drop the `sessionStorage`
  persistence layer entirely. `setTokens`, `getRefreshToken`, and
  `clear` no longer touch `sessionStorage`. The module-scoped
  `refreshToken` cache is retained ONLY for the in-tab tenant-switch
  flow (the body field stays during that single round-trip until 6.3
  below lands).
- SPA `apps/web/src/api/interceptor.ts` `tryRefresh`: stop reading
  `getRefreshToken()`; rely on `credentials: "include"` (already set)
  to ship the cookie. The body POSTed to `/v1/auth/refresh` becomes
  empty. The bail-out condition (line 145) flips from "no refresh
  token in store" to "boot has not produced an access token after one
  refresh attempt".
- SPA `apps/web/src/app.tsx` `bootRefresh`: stop gating on
  `getRefreshToken() === null`. On boot we always attempt one cookie
  refresh; if the cookie is absent or stale the API returns 401 and
  the SPA falls back to `/login` as today.
- SPA `apps/web/src/components/app-sidebar/tenant-switcher.tsx` and
  `apps/web/src/routes/tenants/new.tsx` switch flows: send empty body
  `{}` to `/v1/tenants/{id}/switch`; the cookie carries the refresh
  token. The switch endpoint's request schema becomes
  `refresh_token: str | None` (already nullable in
  `SwitchTenantRequest`, no schema change required) and the server
  prefers the cookie when both are present.
- Backend `SwitchTenantRequest` schema: keep accepting `refresh_token`
  in the body for one cycle (it's already optional) but the use case
  SHALL prefer the cookie. No schema change.
- Tests: update backend integration/e2e tests that assert
  `response.json()["refresh_token"]` to assert the Set-Cookie header
  instead. SPA unit tests for `tokenStore` lose the
  `sessionStorage` cases and gain a "no-op on storage" assertion.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `auth-refresh-token-lifecycle`: add scenarios that pin "JSON body
  excludes refresh_token" and "SPA sessionStorage holds no refresh
  token after login/refresh/switch". The existing requirement text
  already mandates this; the scenarios make it testable.

## Impact

- **API**: response shape contracts for 4 endpoints (login, refresh,
  confirm-signup auto-login, switch). Breaking for any external
  consumer; non-breaking for the SPA after this change ships.
- **Frontend**: `tokenStore.ts`, `interceptor.ts`, `app.tsx`,
  `tenant-switcher.tsx`, `routes/tenants/new.tsx`. The "page reload
  survives" UX is preserved by the cookie + `bootRefresh`.
- **Tests**: backend integration/e2e suites that assert
  `refresh_token` in JSON; SPA unit tests for tokenStore.
- **Security posture**: closes audit finding F-011. After this
  ships, an XSS attacker can no longer read the refresh token from
  JS — the cookie's `HttpOnly` flag is the enforcement boundary.
