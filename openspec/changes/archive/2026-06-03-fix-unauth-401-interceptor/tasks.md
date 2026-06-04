## 1. Sprint doc

- [x] 1.1 Sprint doc already carries the "Sprint follow-up — fix global 401 interceptor on unauthenticated endpoints (2026-06-03)" block (`docs/sprints/03-tenants-and-rls.md`).

## 2. Interceptor — internal discriminator

- [x] 2.1 `RetriableInit.__bearerAttached?: boolean` extended in `apps/web/src/api/interceptor.ts`.
- [x] 2.2 `attachAuth` returns `{ ...init, headers, __bearerAttached: true }` when adding the bearer; early-return for no-token requests leaves `__bearerAttached` undefined.
- [x] 2.3 `fetchWithAuth` captures the single `attached` value and uses it for both the network call and the bearer-attached discriminator.

## 3. 401 branch

- [x] 3.1 `if (attached.__bearerAttached !== true) return first;` placed immediately after the non-401 short-circuit.
- [x] 3.2 Existing `__authRetried` + `tryRefresh` + retry + `handleAuthLost` blocks unchanged for the bearer-attached path.
- [x] 3.3 File-level docblock at the top of `interceptor.ts` documents the invariant.

## 4. Tests

- [x] 4.1 "401 without bearer is passthrough" scenario lives in `apps/web/tests/unit/api/interceptor.test.ts`.
- [x] 4.2 Existing "401 -> refresh succeeds -> retry returns 200" scenario covers the preserved-behaviour invariant.
- [x] 4.3 Existing "refresh fails -> onAuthLost fires and tokens are cleared" scenario covers the auth-lost path.
- [x] 4.4 `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint` all pass.

## 5. Browser smoke

- [ ] 5.1 Wrong-OTP smoke on `/confirm` — deferred (no live dev session in this batch run).
- [ ] 5.2 Used reset-token smoke on `/reset-password` — deferred.
- [ ] 5.3 Bad-credentials smoke on `/login` — deferred.
- [ ] 5.4 Bearer-attached 401 → refresh → retry smoke — deferred.

## 6. Forward-compat

- [x] 6.1 `rg rawFetch apps/web/src` returns only the interceptor itself + the internal refresh wrapper. No auth endpoint silently switched to `rawFetch`.
- [x] 6.2 `openspec validate fix-unauth-401-interceptor --strict` exits 0.
