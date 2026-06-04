## ADDED Requirements

### Requirement: Identity application exceptions translate to RFC-7807 problem details with one status per failure mode

The identity context SHALL translate each typed application exception
to a single, stable `(HTTP status, problem-code, title)` triple in
`apps/api/src/contexts/identity/adapters/inbound/http/errors.py`. The
mapping table below MUST be honoured exactly:

| Exception | HTTP status | `code` | `title` | Extras |
|---|---|---|---|---|
| `InvalidCredentialsError` | 401 | `auth.invalid_credentials` | "Invalid credentials" | — |
| `TokenExpiredError` | 401 | `auth.token_expired` | "Token expired" | — |
| `SignupEmailNotConfirmedError` | 401 | `auth.signup_email_not_confirmed` | "Email confirmation required" | — |
| `LockoutActiveError` | 401 | `auth.lockout_active` | "Account temporarily locked" | `retry_after_seconds` body field |
| `AuthLockoutActiveError` | 429 | `auth.lockout_active` | (Spanish copy in `title`) | `retry_after_seconds` body field, `scope` body field, `Retry-After` header |
| `InvalidConfirmationCodeError` | 400 | `auth.invalid_confirmation_code` | "Invalid confirmation code" | — |
| `InvalidResetCodeError` | 410 | `auth.reset_token_used` | "Reset link no longer valid" | — |
| `ExpiredResetCodeError` | 410 | `auth.reset_token_expired` | "Reset link expired" | — |
| `ResendThrottledError` | 429 | `auth.resend_throttled` | "Resend rate-limited" | `retry_after_seconds` body field, `Retry-After` header |
| `EmailSendError` | 502 | `email.send_failed` | "Email delivery failed" | — |
| `UserNotFoundError` | 404 | `user.not_found` | "User not found" | — |
| `PasswordPolicyError` | 422 | `validation.password_policy` | "Password policy violation" | — |

Every response SHALL carry `Content-Type: application/problem+json`.
Subclasses MUST be matched BEFORE their parents in `to_problem_detail`
(specifically: `ExpiredResetCodeError` BEFORE `InvalidResetCodeError`,
`AuthLockoutActiveError` BEFORE `LockoutActiveError` if any future
subclass relationship is added).

#### Scenario: Wrong OTP on confirm-signup returns 400 with invalid_confirmation_code

- **GIVEN** an account that has registered but not yet confirmed
- **WHEN** the operator submits `POST /v1/auth/confirm-signup` with an OTP that does not match the stored verification hash
- **THEN** the response status is `400`
- **AND** the response body's `code` is `auth.invalid_confirmation_code`
- **AND** the response body's `title` is `Invalid confirmation code`
- **AND** `Content-Type` is `application/problem+json`

#### Scenario: Used password-reset code returns 410 with reset_token_used

- **GIVEN** an account that received a password-reset code and successfully used it once
- **WHEN** the operator submits `POST /v1/auth/password/reset` with the same code a second time
- **THEN** the response status is `410`
- **AND** the response body's `code` is `auth.reset_token_used`

#### Scenario: Expired password-reset code returns 410 with reset_token_expired

- **GIVEN** an account that received a password-reset code more than `password_reset_code_ttl_seconds` ago
- **WHEN** the operator submits `POST /v1/auth/password/reset` with that code
- **THEN** the response status is `410`
- **AND** the response body's `code` is `auth.reset_token_expired`

#### Scenario: Resend within the cooldown returns 429 with resend_throttled and Retry-After

- **GIVEN** an unconfirmed account that has been resent a verification code within the last `_RESEND_COOLDOWN_SECONDS`
- **WHEN** the operator submits `POST /v1/auth/resend-code` for that account again
- **THEN** the response status is `429`
- **AND** the response body's `code` is `auth.resend_throttled`
- **AND** the response body carries a positive integer `retry_after_seconds` field
- **AND** the response carries a `Retry-After` header whose value equals the same integer (as a string)

#### Scenario: Wrong login password still returns 401 with invalid_credentials

- **GIVEN** a confirmed account
- **WHEN** the operator submits `POST /v1/auth/login` with a password that does not match
- **THEN** the response status is `401`
- **AND** the response body's `code` is `auth.invalid_credentials`

#### Scenario: Missing bearer on a protected endpoint still returns 401 with invalid_credentials

- **GIVEN** no `Authorization` header on the request
- **WHEN** the operator calls `GET /v1/me`
- **THEN** the response status is `401`
- **AND** the response body's `code` is `auth.invalid_credentials`

### Requirement: InvalidCredentialsError is reserved for credential-rejection paths only

The application layer SHALL raise `InvalidCredentialsError` ONLY from
call sites that reject a credential the caller presented as proof of
identity. The permitted raise sites are:

- `Authenticate.execute` (wrong password / unknown user on login)
- `RefreshToken.execute` (bad refresh token)
- `verify_token` in the IdP adapters (bad / malformed JWT)
- `change_password` (wrong old password)
- defensive fall-throughs in the IdP adapters for unmapped errors

Wrong-input failures on `confirm-signup`, `password/reset`, and
`resend-code` SHALL raise the typed exceptions above instead, never
`InvalidCredentialsError`.

#### Scenario: confirm-signup never raises InvalidCredentialsError for a bad OTP

- **GIVEN** the local or Cognito IdP adapter receives `confirm_signup` with a bad / expired OTP
- **WHEN** the adapter cannot validate the code
- **THEN** the adapter raises `InvalidConfirmationCodeError`
- **AND** the adapter MUST NOT raise `InvalidCredentialsError` from this path

#### Scenario: confirm_forgot_password never raises InvalidCredentialsError for a bad reset code

- **GIVEN** the local or Cognito IdP adapter receives `confirm_forgot_password` with an invalid / used / expired code
- **WHEN** the adapter cannot validate the code
- **THEN** the adapter raises `InvalidResetCodeError` (or `ExpiredResetCodeError` when the expiry is the explicit reason)
- **AND** the adapter MUST NOT raise `InvalidCredentialsError` from this path

#### Scenario: resend_confirmation never raises InvalidCredentialsError when throttled

- **GIVEN** the local or Cognito IdP adapter receives `resend_confirmation` within the configured cooldown window
- **WHEN** the adapter declines to send a new code because of the throttle
- **THEN** the adapter raises `ResendThrottledError(retry_after_seconds=…)`
- **AND** the adapter MUST NOT raise `InvalidCredentialsError` from this path

### Requirement: ExpiredResetCodeError subclasses InvalidResetCodeError

`ExpiredResetCodeError` SHALL be a subclass of `InvalidResetCodeError`
so that a caller that only needs to detect "the reset code is no
longer usable" can catch the parent type and handle both reasons
uniformly. The HTTP error mapper SHALL still emit distinct status /
code / title triples for each (per the mapping table above).

#### Scenario: Catching the parent matches the subclass

- **GIVEN** a Python `try` block that wraps `confirm_forgot_password` and catches `InvalidResetCodeError`
- **WHEN** the adapter raises `ExpiredResetCodeError`
- **THEN** the `except InvalidResetCodeError` branch handles the exception

### Requirement: ResendThrottledError carries retry-after metadata

`ResendThrottledError` SHALL expose a `retry_after_seconds: int`
attribute that the HTTP adapter uses both as a body extension field
on the problem detail AND as the value of the response `Retry-After`
header. The integer SHALL be positive (clamped to at least 1) so the
header is always interpretable by HTTP clients.

#### Scenario: retry_after_seconds is reflected in both the body and the header

- **GIVEN** `ResendThrottledError(retry_after_seconds=42)` is raised from a route
- **WHEN** the registered exception handler produces the response
- **THEN** the response body contains `"retry_after_seconds": 42`
- **AND** the response carries a `Retry-After: 42` header
