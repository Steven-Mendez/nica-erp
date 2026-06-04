# auth-rate-limit-typed-errors Specification

## Purpose
TBD - created by archiving change rate-limit-typed-error-and-429. Update Purpose after archive.
## Requirements
### Requirement: Rate-limit violations surface as HTTP 429 with a typed error and Retry-After header

The API SHALL surface every rate-limit decision via a typed
`RateLimitedError` mapped to HTTP 429 with code `auth.rate_limited`,
a Spanish title `Demasiados intentos`, a `Retry-After: <N>` header,
and body fields `retry_after_seconds: <N>` and `scope: "<scope>"`. The
endpoint SHALL NOT use 401 or 400 to express rate-limit decisions.
The detail copy SHALL be Spanish.

#### Scenario: Resend cooldown returns 429 with Retry-After

- **GIVEN** an unverified user who has just received a confirmation
  code (last_resend_at = now)
- **WHEN** the SPA calls `POST /v1/auth/resend-code` for the same
  email within the 60-second cooldown
- **THEN** the API SHALL respond `429 Too Many Requests`
- **AND** the response SHALL include a `Retry-After: <N>` header where
  N is a positive integer ≤ 60
- **AND** the body SHALL be a problem-details document with `code:
  "auth.rate_limited"`, `scope: "resend"`, and `retry_after_seconds: N`

#### Scenario: Frontend shows Spanish copy with the seconds interpolated

- **GIVEN** the SPA receives a 429 `auth.rate_limited` with
  `retry_after_seconds: 12`
- **WHEN** the route renders the `FormErrorAlert`
- **THEN** the rendered Spanish copy SHALL read
  `Demasiados intentos. Intenta de nuevo en 12 segundos.`
- **AND** the SPA SHALL NOT navigate to `/login` (the interceptor
  passes 429 through unchanged)

#### Scenario: Login lockout retains its existing scope and code

- **GIVEN** the login-lockout path that already returns
  `auth.lockout_active`
- **WHEN** that path fires
- **THEN** the response SHALL keep `code: "auth.lockout_active"` and
  `scope: "identifier"` — this requirement only covers the
  resend-cooldown and any future generic rate-limit scope

