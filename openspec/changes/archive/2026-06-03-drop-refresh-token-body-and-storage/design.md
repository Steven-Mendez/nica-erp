## Context

The 2026-06-03 hardening introduced `Set-Cookie: nica_erp_rt=…;
HttpOnly; Secure; SameSite=Lax; Path=/v1/auth` on all token-mint
endpoints, and turned on `credentials: "include"` on the SPA's
openapi-fetch client + the `tryRefresh` POST. The cookie is therefore
already being set, sent, rotated, and cleared correctly. What did NOT
land was the **drop of the legacy carrier**:

- The login/refresh/switch JSON bodies still return `refresh_token`.
- The SPA's `tokenStore.ts` still persists that JWT in
  `sessionStorage['nica-erp:refresh-token']` and the interceptor
  still pulls it from the store + POSTs it in the refresh body as
  a "transitional fallback".

The legacy carrier means a single XSS still leaks a 30-day-valid
refresh token even though the cookie is `HttpOnly`. Audit F-011
confirmed this in the running stack (`sessionStorage.getItem(
'nica-erp:refresh-token')` returns the JWT).

Stakeholders:
- The local IdP (`apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py`).
- The HTTP adapter (`apps/api/src/contexts/identity/adapters/inbound/http/router.py`).
- The SPA auth interceptor + tenant-switcher.
- Backend integration / e2e tests that assert response shape.

## Goals / Non-Goals

**Goals:**
- Refresh token leaves the JavaScript runtime entirely. The only
  programmatic surface that can read it is server-side (cookie header
  on POSTs to `/v1/auth/refresh`, `/v1/auth/logout`, etc.).
- Page reload still produces a logged-in SPA via a single boot-time
  call to `/v1/auth/refresh` (no UX regression vs. today).
- Tenant switch and logout continue to work end-to-end with empty
  request bodies — the cookie carries the rotation context.

**Non-Goals:**
- Renaming the access-token audience (deferred per archived tasks 3.1
  / 3.2).
- Implementing a BFF in front of the API.
- Touching the access-token store at all — access stays in JS memory
  (intentional, short-lived).
- Backward-compat for non-SPA callers reading `response.refresh_token`
  — per ADR-0001 the API is private to the monorepo.

## Decisions

### Decision 1 — Stop emitting `refresh_token` in the JSON body

`/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/confirm-signup`
(auto-login branch) and `/v1/tenants/{id}/switch` will drop the
`refresh_token` field from their `TokenResponse`. The `Set-Cookie`
header becomes the sole carrier. Pydantic schema becomes
`access_token: str; id_token: str; token_type: str` (no
`refresh_token`).

**Alternatives considered:**
- Return `refresh_token: None` instead of removing the field. Rejected:
  it leaves a vestigial nullable field that drifts the contract; tests
  would still need updates; future readers wouldn't know the field is
  defunct.
- Gate on a feature flag for one cycle. Rejected: the cookie path is
  already proven end-to-end (it's how the SPA already authenticates
  every request); no rollback path required beyond reverting the
  change.

### Decision 2 — `tokenStore.ts` keeps the in-memory cache, drops sessionStorage

Two-layer thinking:
- The **access token** stays in JS memory only (status quo).
- The **refresh token** loses its in-tab cache and its sessionStorage
  persistence. Functions become:
  - `setTokens(next)` — store access + id only.
  - `getRefreshToken()` — removed (no caller after this change).
  - `clear()` — clears access + id; cookie is cleared by
    `POST /v1/auth/logout`'s `Set-Cookie: …; Max-Age=0`.

**Why not keep the in-tab refresh cache "just in case"?** The cache is
only useful for endpoints that re-send the token in the body. After
this change there are no such endpoints — the cookie always wins.
Holding a copy in JS is exactly the XSS surface we are closing.

### Decision 3 — `interceptor.tryRefresh` POSTs with empty body + credentials

`tryRefresh` becomes:

```ts
const r = await fetch(`${baseUrl}/v1/auth/refresh`, {
  method: "POST",
  credentials: "include",
  headers: { "content-type": "application/json" },
  body: "{}",  // cookie carries the rt
});
```

The 401 path bails as today (returns false, propagates to the original
401 handler). The success path calls `setTokens({ access, id })`.

### Decision 4 — `app.tsx` bootRefresh runs unconditionally on mount

Today: `useState(() => getRefreshToken() === null)` short-circuits the
boot when there's no rt. After this change the SPA can't see the
cookie, so we just call `tryRefresh()` on mount and trust the API to
return 401 if there's nothing to refresh. The 401 path lands the user
on `/login` (same UX as today when sessionStorage was empty).

### Decision 5 — Tenant-switcher and wizard send empty switch body

`useSwitchTenantMutation` (`features/tenants/api/hooks.ts:293`) drops
the `refresh_token` field from its input. The server's
`SwitchTenantRequest` already accepts `refresh_token: str | None`
(see `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`);
the switch use case will read the cookie via the existing
`get_current_user`-style flow.

### Decision 6 — No new scenarios for backward-compat

We are not adding "API still accepts refresh_token in body for
backward compat" as a requirement. The SPA is the only caller; the
server-side schema stays nullable as an accident of the prior
transition, but the use case prefers the cookie.

## Risks / Trade-offs

- **[Risk]** A long-running tab still holds an access token in JS
  memory; XSS can exfil that for up to one hour.
  **Mitigation:** Out of scope — access TTL is the answer (1 h
  rolling expiry). The refresh fix bounds blast radius to one hour
  instead of 30 days.

- **[Risk]** Browser privacy modes (Safari Lockdown, Brave shields
  blocking cookies for first-party iframes) might drop the cookie
  and break refresh.
  **Mitigation:** All four token endpoints share
  `Path=/v1/auth`; `SameSite=Lax` covers the dominant SPA-to-API
  pattern. Edge cases land on `/login` (same UX as a logged-out
  user).

- **[Risk]** A test asserting `response.json()["refresh_token"]` will
  break on the next CI run.
  **Mitigation:** Bundle the test updates in the same PR. The
  integration suite has a small handful of these (audited under
  `tests/integration/api/auth`).

- **[Risk]** The transition keeps the `SwitchTenantRequest` body
  field nullable, which is a small contract smell.
  **Mitigation:** Acceptable for one cycle; a follow-up change can
  remove the field entirely once we confirm no test relies on it.

## Migration Plan

1. Land backend schema + endpoint changes (drop `refresh_token` from
   response models).
2. Land SPA `tokenStore` / `interceptor` / `app.tsx` /
   `tenant-switcher` changes in the **same PR** (response shape and
   client shape must move together).
3. Update affected backend integration + e2e tests in the same PR.
4. Manual smoke: login → reload → switch tenant → logout. Confirm
   `sessionStorage.getItem('nica-erp:refresh-token')` is `null`
   throughout. Confirm cookie persists across reload and clears on
   logout.

**Rollback**: revert the PR. The cookie path has been live since
2026-06-03 so the prior behavior is fully recoverable.
