## Why

F-003: today the resend-cooldown enforcement in
`apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py:259`
raises `InvalidCredentialsError("resend rate-limited")`, which the
inbound adapter maps to **HTTP 401** with
`code:"auth.invalid_credentials"`. The source comment admits this is a
hack:

> The spec mandates rate-limiting; the typed error catalogue does not
> yet ship a dedicated RateLimitedError, so we surface
> InvalidCredentialsError. The HTTP adapter maps this to 400.

Two downstream consequences:

1. **UX collateral damage**: 401 trips the SPA's global interceptor
   (the audit's F-001 chain). Clicking `Reenviar código` twice within
   60 s bounces the user to `/login` with no error context.
2. **API contract**: 401 is semantically wrong for rate-limit. RFC
   6585 defines 429. Mobile/integration clients reading status codes
   for retry decisions are misled.

This change introduces a typed `RateLimitedError`, maps it to
**HTTP 429** with a `Retry-After` header, and rewires the resend
cooldown path to use it.

## What Changes

### Application layer — typed error

- `apps/api/src/contexts/identity/application/errors.py`: new
  `RateLimitedError(scope: str, retry_after_seconds: int)` with code
  `auth.rate_limited`.
- Refactor `local.py:259`: raise `RateLimitedError(scope="resend",
  retry_after_seconds=remaining)` instead of `InvalidCredentialsError`.

### HTTP mapping

- `apps/api/src/contexts/identity/adapters/inbound/http/errors.py`:
  add a handler that maps `RateLimitedError` to:
  - status 429
  - body `{"type":"about:blank","title":"Demasiados intentos","status":429,"detail":"Espera <N> s antes de intentar de nuevo.","code":"auth.rate_limited","retry_after_seconds":<N>,"scope":"<scope>"}`
  - header `Retry-After: <N>`
- The existing login-lockout path (which the audit confirmed returns
  429 with `auth.lockout_active`) stays untouched; it is a separate
  scope (`identifier`) and already correct.

### Frontend — typed error copy

- `apps/web/src/api/errors.ts` problem-code registry:
  - `auth.rate_limited` → Spanish:
    `Demasiados intentos. Espera unos segundos antes de reintentar.`
    Hook the optional `retry_after_seconds` field through the copy:
    `Demasiados intentos. Intenta de nuevo en {{n}} segundos.`
- The interceptor (after `fix-unauth-401-interceptor` ships) treats
  429 as a passthrough error so the SPA can surface it inline.

### Tests

- Backend unit: second resend call within the cooldown raises
  `RateLimitedError`; the inbound adapter renders 429 with `Retry-After`.
- Backend integration: `POST /v1/auth/resend-code` twice fast →
  second response is 429 with the expected header and body.
- Frontend Vitest: MSW returns 429 with `auth.rate_limited` → the
  inline alert renders the Spanish copy with the seconds interpolated.

## Non-goals

- IP-scoped rate-limit for resend (G14 covers the broader login
  lockout backoff and IP scope).
- Refactoring the existing login-lockout scope's wire format.
- Adding rate-limit to forgot-password (that endpoint is intentionally
  enumeration-safe; a separate change could add silent throttling).
