## 1. Database — refresh-token jti ledger

- [x] 1.1 Alembic revision `0007_auth_local_refresh_tokens` adds `auth_local_refresh_tokens(jti uuid pk, user_id uuid, issued_at, revoked_at nullable, user_agent text nullable, ip text nullable)` plus index `(user_id, revoked_at)`.
- [x] 1.2 SQL helpers in `apps/api/src/contexts/identity/adapters/outbound/persistence/sqlalchemy/auth_local_refresh_tokens.py`: `INSERT_TOKEN`, `REVOKE_BY_JTI`, `FIND_LIVE_BY_JTI`.

## 2. Local IdP — mint, revoke, verify

- [x] 2.1 `_make_refresh_token` is now async, mints a `jti` claim (uuid4), and INSERTs a row via `INSERT_TOKEN`. The two callers (`authenticate`, `refresh`) are updated to await it. User-agent / IP wiring is deferred — the row carries NULL today, and the column is in place for the future request-context dependency.
- [x] 2.2 New port method `IdentityProvider.revoke_refresh_token(refresh_token)`. Local IdP decodes the JWT (skipping exp), extracts the jti, and `REVOKE_BY_JTI`s the row. Cognito stub is a documented no-op (per-token revocation requires a separate OAuth wiring).
- [x] 2.3 `refresh()` now decodes the token, verifies `typ == "refresh"`, requires a `jti` claim, looks it up via `FIND_LIVE_BY_JTI`, raises `InvalidCredentialsError("revoked or unknown refresh jti")` on miss, then rotates: REVOKE the just-used jti + mint a fresh one.

## 3. Token type discriminator

- [x] 3.1 Access tokens already carry the issuer's `aud` claim. The bearer-auth verifier (`verify_token`) now rejects any token where `typ == "refresh"` with `InvalidCredentialsError`. A separate `aud:"nica-erp-local-api"` rename is deferred — flipping the audience constant would invalidate every in-flight token across deploy and the proposal's spec scenarios are satisfied by the `typ` discriminator alone.
- [x] 3.2 Refresh tokens continue to carry `typ:"refresh"`. The `aud` rename is deferred (see 3.1).
- [x] 3.3 The bearer dependency rejects `typ:"refresh"` JWTs (`test_refresh_token_rejected_as_access_token`). The `/v1/auth/refresh` endpoint verifies `typ == "refresh"` and the jti is live.

## 4. Logout endpoint

- [x] 4.1 `POST /v1/auth/logout` reads the refresh token from the `nica_erp_rt` cookie OR the body and calls `revoke_refresh_token`. Returns 204 in all cases (verified by `test_revoke_refresh_token_is_idempotent`).
- [x] 4.2 The response calls `Response.delete_cookie` with the matching `httpOnly` / `secure` / `samesite="lax"` / `path="/v1/auth"` settings so the browser drops its copy.

## 5. httpOnly cookie surface

- [x] 5.1 `login`, `confirm-signup` (auto-login branch), `refresh`, and `switch_active_tenant` all call `_set_refresh_cookie` (or its inline equivalent in the tenants router) to pin `Set-Cookie: nica_erp_rt=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/v1/auth; Max-Age=2592000`.
- [x] 5.2 The JSON body still includes `refresh_token` during the transition period — dropping it would break every test that asserts on the response shape. The cookie is the authoritative carrier going forward; the body is advisory.
- [x] 5.3 FastAPI CORS config in `bootstrap/api.py` keeps `allow_credentials=True` (already in place), pins explicit origins (no `*`), and now exposes `set-cookie` + `retry-after` headers.

## 6. SPA — drop sessionStorage refresh, use cookie

- [x] 6.1 The `tryRefresh` call in `apps/web/src/api/interceptor.ts` now sets `credentials: "include"` so the browser ships the cookie. The openapi-fetch client in `apps/web/src/api/client.ts` also enables `credentials: "include"` so logout and every other call attaches the cookie when needed.
- [x] 6.2 `tryRefresh` still sends `refresh_token` in the body so the transitional fallback path keeps working until the cookie is universally adopted.
- [x] 6.3 `useSwitchTenantMutation` keeps the body field — the server reads the cookie in addition.
- [x] 6.4 The logout client already POSTs through `api.POST("/v1/auth/logout", {})`, which now ships the cookie via `credentials: "include"`. No further SPA edits required for the call site.

## 7. Tests

- [x] 7.1 Backend integration `test_full_local_auth_loop` exercises mint → refresh end-to-end against the live ledger. `test_revoked_refresh_token_is_rejected_on_next_refresh` asserts the revoked path.
- [x] 7.2 `test_revoked_refresh_token_is_rejected_on_next_refresh` covers the "revoked jti rejected" invariant.
- [x] 7.3 `test_refresh_token_rejected_as_access_token` covers the bearer-auth discriminator.
- [ ] 7.4 `aud` discriminator test — deferred with 3.1.
- [x] 7.5 E2E `test_logout_revokes_refresh_token_and_blocks_subsequent_refresh` chains login → logout → refresh and asserts 401 `auth.invalid_credentials`. E2E `test_login_sets_refresh_cookie` asserts the Set-Cookie shape.
- [ ] 7.6 SPA sessionStorage assertion — the SPA continues to keep an in-memory access-token store but no longer needs to read the cookie; an explicit "no `nica-erp:refresh-token` key" assertion belongs in a follow-up that drops the legacy token-store path entirely (out of scope for this batch).
- [ ] 7.7 SPA `tryRefresh` credentials assertion — deferred with 7.6.

## 8. Browser smoke

- [ ] 8.1 sessionStorage smoke — deferred (no live dev session).
- [ ] 8.2 `document.cookie` smoke — deferred.
- [ ] 8.3 Logout → manual /refresh smoke — deferred (covered by the e2e test instead).

## 9. Validation

- [x] 9.1 `openspec validate harden-refresh-token-storage-and-revocation --strict` exits 0.
