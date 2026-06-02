## Why

The QA audit's security and stability sections both pointed at the
authentication surface. Three findings cluster naturally:

1. **No rate limiting on `/v1/auth/login`.** The audit drove 11+
   consecutive failed login attempts against the deployed API and
   received `401 invalid_credentials` every time with no lockout, no
   slowdown, and no captcha challenge. This is an OWASP A07:2021
   regression: credential-stuffing and password-spray attacks succeed
   against any operator whose password is on a public breach list.
   The identity context already emits `AuthenticationFailed` domain
   events (see
   `apps/api/src/contexts/identity/application/use_cases/authenticate.py`)
   so the data needed to count failures by IP and by identifier is
   already flowing — it is simply not being consumed.
2. **Confirm-signup silent redirect on bad OTP.** A wrong code on
   `/confirm` produces a `401 Unauthorized` from
   `POST /v1/auth/confirm-signup`; the SPA mutation in
   `apps/web/src/features/auth/api/hooks.ts` (`useConfirmSignupMutation`)
   has no `onError` and the route bounces to `/login`. The operator
   has no feedback that the code was wrong, only that "something logged
   me out." The same pattern appears on the password-reset flow: a
   replayed (already-used) reset token returns a backend error that the
   reset-password route ignores, redirecting to `/login` as if reset
   succeeded.
3. **No correlated UI mapping for `auth.*` problem codes.** The shared
   problem-error catalog at `apps/web/src/api/errors.ts` already
   defines `auth.token_expired`, `auth.lockout_active`,
   `auth.signup_email_not_confirmed`, etc., but the auth route
   components do not consult it — they treat any non-2xx as "redirect
   to login." This is the upstream cause of both 2 and the audit's
   "replay token" finding, and it leaves us with no shared place to
   map future auth error codes.

## What Changes

### Backend — `/v1/auth/login` rate limiting

- Introduce a `LoginAttemptThrottle` application-service port in
  `apps/api/src/contexts/identity/application/` with two counters:
  per-source-IP (sliding window) and per-identifier (the submitted
  email), each independently triggering a `auth.lockout_active`
  problem response (HTTP 429) once thresholds are exceeded.
- Default thresholds: **5 failures per identifier per 15 minutes**
  (resets on successful auth) and **20 failures per source-IP per 15
  minutes** (resets on hour). Both are configurable via the bootstrap
  settings so the local-dev profile can use looser limits during e2e.
- Adapter implementation: a `RedisLoginAttemptThrottle` outbound
  adapter in `apps/api/src/contexts/identity/adapters/outbound/`. The
  AWS profile already provisions Redis (used by the session store);
  the local profile uses the in-memory dict adapter we already use for
  the e2e test transport. **AWS access uses the named profile
  `nica-erp`** — no default-profile fallback.
- The lockout response MUST carry `Retry-After` headers and the
  existing `auth.lockout_active` problem code so the SPA can render a
  localized "Demasiados intentos, espera unos minutos" message
  without inventing a new code.
- The lockout counter is incremented inside the existing
  `AuthenticateUseCase` orchestration so it cannot be bypassed by
  callers — it lives at the boundary between the HTTP adapter and the
  use case, not inside the inbound adapter.

### Frontend — surface auth problem codes instead of redirecting

- `useConfirmSignupMutation`, `useResetPasswordMutation`, and
  `useForgotPasswordMutation` MUST expose `mutation.error` to their
  route components and MUST NOT trigger a navigation on error. The
  current navigation calls in `routes/confirm.tsx` etc. move from
  `onSettled` to `onSuccess`.
- Each affected route renders an inline form-level error block —
  `<FormErrorAlert />` (new shared component under
  `components/form/`) — that translates the problem code via the
  existing `apps/web/src/api/errors.ts` catalog. Required mappings:
  - `auth.invalid_credentials` → "Correo o contraseña incorrectos."
  - `auth.lockout_active` → "Demasiados intentos. Intenta de nuevo en
    {minutos} minutos." (uses `Retry-After`)
  - `auth.invalid_confirmation_code` → "Código incorrecto o
    expirado. Solicita uno nuevo."
  - `auth.reset_token_used` → "Este enlace ya fue utilizado. Solicita
    uno nuevo."
  - `auth.reset_token_expired` → "El enlace expiró. Solicita uno
    nuevo."
- The `/login` form gains a visible "Demasiados intentos…" banner when
  the API returns 429 with `auth.lockout_active`, including the
  countdown derived from `Retry-After`.

### Tests

- Backend: pytest cases under `apps/api/tests/integration/` for
  identifier-locked, IP-locked, and lockout-expiry-with-success
  scenarios. Use the in-memory throttle adapter and synthesize time
  via the existing `Clock` port (no `time.sleep`).
- Frontend: Vitest integration tests under
  `apps/web/tests/integration/` for each error code → Spanish copy
  mapping. Use MSW handlers that return the actual `application/
  problem+json` payloads the backend will emit.

## Capabilities

### New Capabilities

- `auth-login-rate-limiting`: counter strategy, thresholds, problem
  code, `Retry-After` semantics, and how the lockout interacts with
  successful authentication.
- `frontend-auth-error-feedback`: contract that auth mutations expose
  errors, the route renders them inline, and the problem-code →
  Spanish-copy mapping for the confirm-signup, reset-password,
  forgot-password, and login surfaces.

### Modified Capabilities

_(none — backend identity-* specs are not currently materialized in
`openspec/specs/`; new capabilities are introduced rather than
amending archived deltas.)_

## Impact

- **Code (backend):**
  - `apps/api/src/contexts/identity/application/` — new
    `LoginAttemptThrottle` port; `AuthenticateUseCase` consumes it.
  - `apps/api/src/contexts/identity/adapters/outbound/` — Redis
    adapter and in-memory adapter.
  - `apps/api/src/bootstrap/container.py` — wire the adapter into the
    composition root, switching by profile.
  - `apps/api/src/contexts/identity/adapters/inbound/http/router.py` —
    map throttle exception to 429 + `Retry-After` + problem code.
- **Code (frontend):**
  - `apps/web/src/features/auth/api/hooks.ts` — remove navigation from
    `onSettled`; expose `error` cleanly.
  - `apps/web/src/routes/confirm.tsx`, `reset-password.tsx`,
    `forgot-password.tsx`, `login.tsx` — render inline error block.
  - `apps/web/src/api/errors.ts` — confirm/extend the problem-code
    table (no new fields, just verify each code has a Spanish copy).
  - New `apps/web/src/components/form/form-error-alert.tsx`.
- **Infra:** Terraform module that provisions Redis already exists
  (sprint 03); no new infra. The AWS profile remains `nica-erp`.
- **APIs:** `POST /v1/auth/login` now returns 429 +
  `application/problem+json` with `code: auth.lockout_active` and a
  `Retry-After` integer-seconds header. No breaking change to 200/401
  responses.
- **Docs:** `docs/05-security.md` gains a short section on the
  throttle thresholds and how to tune them per environment.
