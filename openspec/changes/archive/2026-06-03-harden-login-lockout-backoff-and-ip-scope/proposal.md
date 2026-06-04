## Why

F-023: the audit confirmed the existing login-lockout fires after
5 failed attempts but the lockout duration is only **3 seconds** with
`scope:"identifier"`. The 429 response carries a Spanish title
(`Cuenta temporalmente bloqueada`) and `retry_after_seconds`, which is
good. But:

- 3 s is too short to deter credential stuffing — wait 3 s, send 5
  more, repeat. Effective ceiling ≈ 100 attempts/min/email.
- There is no IP-scoped lockout. An attacker rotating identifiers
  (spraying many emails from one IP) bypasses the per-identifier
  scope entirely.

This change adds **exponential backoff** to the identifier-scope
lockout and introduces a parallel **IP-scope** lockout that fires
independently.

## What Changes

### Backend — exponential identifier-scope backoff

- The identifier-scope lockout counter SHALL track:
  - Number of failed attempts in the current "burst" (resets on
    successful login).
  - Time since the most recent lockout for the same identifier.
- Backoff schedule: 3 s → 30 s → 300 s (5 min) → 1800 s (30 min) →
  manual unlock required (admin tooling out of scope for this
  change; treat `manual unlock required` as a documented end-state
  for now).
- The 429 response continues to include `retry_after_seconds`. Spanish
  copy continues as today.

### Backend — IP-scope lockout

- Track failed-login counters keyed by `ip` independently of
  identifier. The IP-scope SHALL fire after 20 failed attempts within
  10 minutes from the same IP regardless of identifier.
- 429 response uses `scope:"ip"` so the SPA / clients can distinguish.
  Body copy: `Demasiados intentos desde esta red. Espera <N> s antes
  de intentar de nuevo.`
- The IP-scope SHALL NOT leak which identifier triggered the lockout
  (defense against probing).

### Backend — storage choice

- For local dev, use an in-process keyed counter (existing module
  already does identifier-scope this way — extend it).
- The spec MAY note Redis as the production choice; actual Redis
  wiring is out of scope here.

### Tests

- Backend unit (`apps/api/tests/unit/contexts/identity/...`):
  - Identifier-scope: 5 failures → 3 s lockout; another 5 failures
    after lockout expiry → 30 s lockout; etc.
  - IP-scope: 20 failures from one IP across different identifiers
    → 429 `scope:"ip"`.
- Backend integration: drive 25 failed logins for `eve@evil.test`
  from a single client; observe lockout escalation.

## Non-goals

- Captcha / hCaptcha integration.
- Admin tool to unlock manually-locked accounts.
- Wiring to a real Redis (the existing in-process store stays for the
  local IdP path).
- Lockout on registration, password reset, or invitation accept — out
  of scope.
