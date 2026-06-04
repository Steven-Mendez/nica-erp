# auth-password-policy Specification

## Purpose
TBD - created by archiving change unify-password-policy-min-length. Update Purpose after archive.
## Requirements
### Requirement: A single canonical password policy applies on every password-acceptance path

The system SHALL enforce one canonical password policy on every
endpoint that accepts a password: at least 12 characters, at most 128
characters, at least one uppercase letter, at least one lowercase
letter, at least one digit, and at least one non-alphanumeric symbol.
This rule SHALL apply to `POST /v1/auth/register`,
`POST /v1/auth/confirm-signup` (auto-login branch),
`POST /v1/auth/password/reset`, and `POST /v1/auth/change-password`.

#### Scenario: Reset accepts a 12+ strong password

- **GIVEN** a valid reset token for `owner1@audit.test`
- **WHEN** the SPA calls `POST /v1/auth/password/reset` with
  `new_password: "Owner1!AuditX2026"` (16 chars, mixed classes)
- **THEN** the API SHALL respond `204 No Content`

#### Scenario: Reset rejects an 8-char password

- **GIVEN** the same reset token
- **WHEN** the SPA submits `new_password: "Short1!a"` (8 chars)
- **THEN** the API SHALL respond `422 auth.weak_password`
- **AND** the body SHALL include `failed_rules: ["min_length"]`

#### Scenario: Signup rejects a password missing a symbol

- **GIVEN** a fresh `POST /v1/auth/register` attempt
- **WHEN** the body carries `password: "NoSymbol123A"` (12 chars,
  upper/lower/digit but no symbol)
- **THEN** the API SHALL respond `422 auth.weak_password`
- **AND** the body SHALL include `failed_rules` containing
  `symbol_missing`

### Requirement: The SPA renders the canonical policy from a single source of truth

The SPA SHALL render the password-policy help text from a single
exported constant, applied identically on `/signup` and
`/reset-password`. The client-side zod schema SHALL also be the
shared canonical schema. The string `8+ caracteres` SHALL NOT appear
anywhere in the SPA.

#### Scenario: Signup and reset-password show the same policy text

- **GIVEN** the SPA is on `/signup`
- **WHEN** the password input renders its help text
- **THEN** the rendered Spanish text SHALL be `12+ caracteres con
  mayúscula, minúscula, dígito y símbolo.`
- **AND** the same text SHALL appear under the password input on
  `/reset-password`

#### Scenario: Client-side schema rejects a 10-char password

- **GIVEN** the SPA's signup form
- **WHEN** the operator types a 10-char password and clicks Crear cuenta
- **THEN** the SPA SHALL render a Spanish field-level error
- **AND** SHALL NOT issue a `POST /v1/auth/register` call

