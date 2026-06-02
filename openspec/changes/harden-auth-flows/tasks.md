## 1. Backend — LoginAttemptThrottle port and adapters

- [ ] 1.1 Define `LoginAttemptThrottle` Protocol and `LockoutState` value object in `apps/api/src/contexts/identity/application/login_attempt_throttle.py`.
- [ ] 1.2 Add `AuthLockoutActive(retry_after_seconds: int, scope: Literal["identifier","ip"])` exception in `apps/api/src/contexts/identity/application/errors.py`.
- [ ] 1.3 Implement `InMemoryLoginAttemptThrottle` under `apps/api/src/contexts/identity/adapters/outbound/login_attempt_throttle_memory.py` with sliding-window semantics and configurable thresholds.
- [ ] 1.4 Implement `RedisLoginAttemptThrottle` under `apps/api/src/contexts/identity/adapters/outbound/login_attempt_throttle_redis.py` using `ZADD` / `ZREMRANGEBYSCORE` / `ZCARD` for the sliding window, and ensure fail-open behavior on connection error.
- [ ] 1.5 Add unit tests under `apps/api/tests/unit/contexts/identity/` covering each adapter: threshold, window slide, success-clears-identifier, IP-counter-independence, fail-open on Redis error.

## 2. Backend — Use case integration

- [ ] 2.1 Update `AuthenticateUseCase` in `apps/api/src/contexts/identity/application/use_cases/authenticate.py` to depend on `LoginAttemptThrottle` and call `check` → password compare → `record_failure` / `record_success` in the order documented in the spec.
- [ ] 2.2 Update `apps/api/src/bootstrap/container.py` to wire `InMemoryLoginAttemptThrottle` into the local-dev profile and `RedisLoginAttemptThrottle` into the AWS profile. AWS Redis access uses the named profile `nica-erp`.
- [ ] 2.3 Map `AuthLockoutActive` to a 429 + `auth.lockout_active` problem doc + `Retry-After` header in `apps/api/src/contexts/identity/adapters/inbound/http/router.py`.
- [ ] 2.4 Add bootstrap settings entries for `LOGIN_THROTTLE_IDENTIFIER_LIMIT`, `LOGIN_THROTTLE_IDENTIFIER_WINDOW_SECONDS`, `LOGIN_THROTTLE_IP_LIMIT`, `LOGIN_THROTTLE_IP_WINDOW_SECONDS` with sane defaults.

## 3. Backend — Integration tests

- [ ] 3.1 pytest integration under `apps/api/tests/integration/` covering identifier-locks-after-5-fails (against the FastAPI test client + in-memory adapter), with synthesized time via the `Clock` port.
- [ ] 3.2 Test IP-locks-after-20-fails-across-identifiers.
- [ ] 3.3 Test that 200 OK login resets the identifier counter but not the IP counter.
- [ ] 3.4 Test that the 429 response includes `Retry-After` and the `auth.lockout_active` code, and that the Spanish title/detail match the catalog.
- [ ] 3.5 Test fail-open: with a stub throttle that raises, `POST /v1/auth/login` still serves 200 / 401 normally.

## 4. Frontend — Problem-code registry & FormErrorAlert

- [ ] 4.1 Extend `apps/web/src/api/errors.ts` with a `messageForProblem` function covering every code listed in `frontend-auth-error-feedback/spec.md`.
- [ ] 4.2 Add the `auth.lockout_active` Retry-After templating utility and unit-test ceiling/clamp behavior.
- [ ] 4.3 Create `apps/web/src/components/form/form-error-alert.tsx` with `role="alert"` and `aria-live="assertive"`.
- [ ] 4.4 Vitest unit test for `FormErrorAlert`: null → nothing, ApiProblem → Spanish copy, unknown → generic fallback.
- [ ] 4.5 Vitest unit test that every code currently emitted by `apps/api/src/contexts/identity/adapters/inbound/http/router.py` has an entry in the registry (parametric over a fixture list).

## 5. Frontend — Mutation & route updates

- [ ] 5.1 In `apps/web/src/features/auth/api/hooks.ts`, move navigation from `onSettled` to `onSuccess` for `useLoginMutation`, `useConfirmSignupMutation`, `useForgotPasswordMutation`, `useResetPasswordMutation`.
- [ ] 5.2 Update `apps/web/src/routes/login.tsx` to render `<FormErrorAlert error={loginMut.error} />` and remove any redirect on error.
- [ ] 5.3 Update `apps/web/src/routes/confirm.tsx` to render `<FormErrorAlert>` and ensure `/login` redirect happens only on success.
- [ ] 5.4 Update `apps/web/src/routes/forgot-password.tsx` and `apps/web/src/routes/reset-password.tsx` analogously.

## 6. Frontend — Integration tests

- [ ] 6.1 Vitest integration under `apps/web/tests/integration/auth-confirm-bad-otp.test.tsx`: MSW returns 401 + `auth.invalid_confirmation_code`; assert inline alert renders Spanish copy and route stays on `/confirm`.
- [ ] 6.2 Vitest integration `apps/web/tests/integration/auth-reset-token-used.test.tsx`: MSW returns 400 + `auth.reset_token_used`; assert alert renders, no redirect.
- [ ] 6.3 Vitest integration `apps/web/tests/integration/auth-login-lockout.test.tsx`: MSW returns 429 + `auth.lockout_active` + `Retry-After: 600`; assert Spanish copy includes `"10 minutos"`.
- [ ] 6.4 Vitest integration `apps/web/tests/integration/auth-login-success-clears-error.test.tsx`: previous error renders, then a successful login clears the alert and navigates to `/dashboard`.

## 7. Documentation

- [ ] 7.1 Add a "Login throttle" subsection to `docs/05-security.md` documenting the thresholds, scopes, fail-open Redis behavior, and how to tune via bootstrap settings. No reference to `openspec/changes/*`.
- [ ] 7.2 Add a "Form errors" subsection to `docs/09-frontend.md` describing `FormErrorAlert` and the registry rule.

## 8. Verification

- [ ] 8.1 `pnpm --filter web typecheck && pnpm --filter web test` — green.
- [ ] 8.2 `cd apps/api && pytest` (or the workspace runner) — green.
- [ ] 8.3 Manual smoke against the local stack: 6 failed logins to the same identifier returns 429 with `Retry-After`; the SPA renders the Spanish lockout copy.
- [ ] 8.4 Manual smoke: stop Redis in the AWS dev environment (or simulate via the adapter test seam), confirm `/v1/auth/login` continues to serve 401 for bad creds and 200 for good ones, with a warning log entry.
