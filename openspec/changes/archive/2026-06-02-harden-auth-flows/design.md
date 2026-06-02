## Context

Identity is a hexagonal context in `apps/api/src/contexts/identity/`.
`AuthenticateUseCase`
(`apps/api/src/contexts/identity/application/use_cases/authenticate.py`)
already orchestrates the password-check + token-issue flow and emits
domain events (`AuthenticationFailed`, `AuthenticationSucceeded`). The
inbound HTTP router at
`apps/api/src/contexts/identity/adapters/inbound/http/router.py` maps
exceptions to RFC 7807 problem documents using the shared
`application/problem+json` error catalog. The frontend mirrors the
catalog in `apps/web/src/api/errors.ts`, which already includes
`auth.lockout_active`, `auth.token_expired`,
`auth.signup_email_not_confirmed`, etc.

What is missing:

- A throttle that consumes the failure signal and converts it into a
  lockout decision. The `auth.lockout_active` code exists in the
  catalog but no code path emits it.
- The SPA mutations for confirm-signup, reset-password, and
  forgot-password do not surface their errors to the form — they
  navigate (in `onSettled`) regardless of outcome.

## Goals / Non-Goals

**Goals:**

- Cap the cost of credential-stuffing and password-spray on
  `/v1/auth/login` to a level where automated tools are unrewarding
  while not locking out legitimate operators who fat-finger their
  password.
- Surface authentication failures to the operator inline, with
  Spanish copy, on every auth-related form, instead of silent
  redirects to `/login`.
- Make the problem-code → Spanish-copy translation a single registry
  so future auth codes get added in one place.

**Non-Goals:**

- IP geofencing or device fingerprinting. Out of scope for this round.
- Adding MFA. Separate roadmap item.
- Replacing the password-reset token format. The reset-token-used and
  reset-token-expired conditions are already correctly handled by the
  backend; this change only fixes the SPA's silent redirect.
- Adding CAPTCHA. Considered but the throttle alone satisfies the
  OWASP A07 minimum; CAPTCHA is a UX cost we'd rather not pay yet.

## Decisions

### Decision 1 — Two independent counters (identifier + source-IP), both can trigger lockout

Considered options:

- Identifier-only: cleanest UX (an attacker who knows one email locks
  only that account) but trivially bypassed by rotating emails in a
  password-spray attack.
- IP-only: handles password-spray but lets a determined attacker who
  controls many IPs hammer one account.
- Both, chosen: each counter increments on failure; either crossing
  its threshold returns `auth.lockout_active` with `Retry-After`.

Thresholds:

- Identifier: 5 failures / 15 minutes, sliding window. Reset on
  successful authentication for that identifier.
- IP: 20 failures / 15 minutes, sliding window. Resets on the hour;
  does not reset on success (a shared NAT exit should not be
  unlocked by one user's correct login).

Both thresholds are read from the bootstrap settings so the local-dev
profile can use looser limits during e2e (e.g. 100 / 5 minutes for
both) without per-env code branches.

### Decision 2 — Throttle is an application-service port, Redis adapter for AWS, in-memory for local

`LoginAttemptThrottle` lives in
`apps/api/src/contexts/identity/application/` as a Protocol with
three methods: `record_failure(identifier, source_ip, when) -> None`,
`record_success(identifier) -> None`, and `check(identifier,
source_ip, when) -> LockoutState`. The use case calls `check` before
attempting the password compare; if `LockoutState.locked`, it raises
`AuthLockoutActive(retry_after_seconds)` which the HTTP router maps to
429 + the problem doc.

Adapters:

- `InMemoryLoginAttemptThrottle` — used in tests and the local-dev
  bootstrap profile. Storage is a `dict[str, list[float]]` keyed by
  identifier / IP, pruned on `check`.
- `RedisLoginAttemptThrottle` — used in the AWS profile.
  Implementation strategy: `ZADD` the timestamp into a sorted set per
  key with TTL 15 minutes; `ZREMRANGEBYSCORE` prunes; `ZCARD` is the
  current count. Two keys per failure: `login:fail:id:{identifier}`
  and `login:fail:ip:{source_ip}`. Successful logins `DEL` the
  identifier key only.

The composition root in `apps/api/src/bootstrap/container.py`
chooses the adapter via the existing profile switch.

### Decision 3 — Lockout check happens inside the use case, not the HTTP adapter

We deliberately do not gate the lockout at the HTTP layer
(middleware, decorator on the route handler). Reasons:

- The use case is the authentication boundary; bypassing it via a
  different inbound adapter (CLI, scheduled job) should still get the
  throttle.
- The `Clock` port is already wired into the use case for time-based
  decisions, so the sliding window has a testable, deterministic
  time source.
- Bonus: tests for the throttle don't need an ASGI client.

### Decision 4 — `Retry-After` integer seconds, derived from window-end - now

When `check` returns `locked`, it includes
`retry_after_seconds = max(window_end - now, 1)`. The HTTP router
sets `Retry-After: <seconds>`. The frontend reads the header and
formats it as `"en X minutos"` (rounded up).

### Decision 5 — Frontend surfaces errors via `mutation.error` and an inline `<FormErrorAlert>`; no navigation on failure

Today the mutations do `navigate({ to: "/dashboard" })` (or similar)
in `onSettled`. We change this to:

- `onSuccess`: do the navigation.
- `onError`: nothing — the form reads `mutation.error` and renders
  `<FormErrorAlert error={mutation.error} />`.

`<FormErrorAlert>` is a tiny component that takes an unknown error,
extracts the problem code if present (`ApiProblem`), and looks up the
Spanish copy in a registry. Unknown errors fall through to
`"Ocurrió un error. Intenta de nuevo."`

### Decision 6 — Centralize problem-code → Spanish-copy mapping in `apps/web/src/api/errors.ts`

The catalog already has the codes; we add (or confirm) Spanish copy
fields next to each. A new exported function
`messageForProblem(problem: ApiProblem): string` returns the Spanish
copy and is the only path used by `<FormErrorAlert>`. This avoids
copy drift across routes.

For `auth.lockout_active`, the copy includes the formatted
`Retry-After` window: `"Demasiados intentos. Intenta de nuevo en {n}
minutos."` (rounds up; clamped to ≥ 1 minute).

## Risks / Trade-offs

- **Risk:** Legitimate operator hits the 5-failure identifier
  threshold after a series of typos and is locked out for 15
  minutes with no recovery path. → **Mitigation:** the
  forgot-password flow is unaffected by the throttle (it doesn't go
  through `AuthenticateUseCase`), so a locked-out operator can reset
  and log in. The lockout copy mentions the reset path.
- **Risk:** Shared NAT exits hit the IP threshold and block a
  building. → **Mitigation:** the IP threshold is high (20 / 15
  minutes) and IP lockouts are 15-minute windows; a single mistyped
  password from many users in one office is well below the
  threshold. Tunable per environment.
- **Risk:** Redis outage in AWS would mean the throttle silently
  fails open or fails closed. → **Mitigation:** the adapter MUST
  fail **open** on connection errors (log + allow the request) so a
  Redis outage does not lock everyone out. The connection-error path
  is covered by a unit test.
- **Risk:** Frontend `<FormErrorAlert>` displays raw English problem
  codes if a backend code is missing from the registry. →
  **Mitigation:** `messageForProblem` defaults to the generic Spanish
  fallback; a Vitest test asserts every code currently emitted by
  the identity router has a Spanish entry.
- **Trade-off:** The 15-minute window is intentionally short to keep
  legitimate-user friction low. A determined attacker can wait it
  out. We accept this as the right balance for an MVP; the next
  iteration adds CAPTCHA or progressive-delay if telemetry shows it
  is being routinely abused.

## Migration Plan

Single deploy, no data migration. The throttle starts fresh on first
boot. Rollback: remove the throttle port from the use case (one-line
revert in the use case + composition root). Frontend changes are
purely additive — no breaking change to existing forms.

## Open Questions

- Should successful login from a previously-rate-limited IP partially
  decay the IP counter (e.g. halve it)? Current decision: no — IPs
  decay on time only.
- Should we expose a `/v1/auth/throttle-status` endpoint so the
  frontend can pre-disable the submit button if the IP is already
  locked? Defer; current `Retry-After` after the 429 is enough
  for now.
- Confirm the actual problem code emitted by the backend for
  duplicate-pending-invitation — `polish-empresa-ux-and-a11y`
  references it but the auth catalog does not own it.
