## ADDED Requirements

### Requirement: `IdentityProviderLocal` implements every port method

The `IdentityProviderLocal` adapter SHALL implement the eleven methods
declared on `IdentityProvider`. It SHALL persist all state to the
`auth_local_users` table via the active
`SqlAlchemyUnitOfWork.current_session` — it MUST NOT open its own
connection. The adapter SHALL be selected by
`bootstrap.container.build_identity_provider()` only when
`settings.app_env == "local"`. The adapter SHALL live in
`contexts.identity.adapters.outbound.identity_provider.local`.

#### Scenario: Adapter satisfies the port at runtime

- **WHEN** `isinstance(IdentityProviderLocal(...), IdentityProvider)`
  is evaluated
- **THEN** the expression SHALL be `True`

### Requirement: bcrypt-hashed passwords, SHA-256 verification codes

The adapter SHALL store passwords as bcrypt hashes with cost
`rounds=12` and SHALL store verification codes as SHA-256 hashes (the
plaintext code is sent over email and immediately discarded). The
`auth_local_users` row SHALL never contain the plaintext password or
the plaintext code.

#### Scenario: Plaintext password is never persisted

- **WHEN** `register(...)` is called with `password="Demo1234!@xy"`
- **THEN** the `auth_local_users.password_hash` column for the new row
  SHALL match the bcrypt verifier for `"Demo1234!@xy"` and SHALL NOT
  equal `"Demo1234!@xy"` literally

### Requirement: HS256 JWT with the canonical claim shape

`authenticate(...)` and `refresh(...)` SHALL return JWTs signed with
HS256 against `settings.local_jwt_secret`. The access-token claims
SHALL include exactly `sub`, `email`, `email_verified`,
`custom:active_tenant`, `aud`, `iss`, `exp`, `iat`. `aud` SHALL equal
`"nica-erp-local"`; `iss` SHALL equal `"nica-erp-local-idp"`. Access
tokens SHALL have a TTL equal to `settings.jwt_access_ttl_seconds`
(default 3600 s); ID tokens SHALL share the same TTL as access tokens
(per [`docs/06-security-model.md` §TTLs](../../../../docs/06-security-model.md#ttls):
access 1 h, ID 1 h); refresh tokens SHALL have a TTL equal to
`settings.jwt_refresh_ttl_seconds` (default 2_592_000 s, 30 days).

#### Scenario: Access token decodes with the expected claim set

- **WHEN** an access token returned by a successful `authenticate(...)`
  is decoded with `LOCAL_JWT_SECRET`
- **THEN** the claims SHALL include all eight keys above, with `aud =
  "nica-erp-local"`, `iss = "nica-erp-local-idp"`, and `exp - iat ==
  3600`

#### Scenario: ID token TTL matches the access token TTL

- **WHEN** an ID token returned by a successful `authenticate(...)`
  is decoded with `LOCAL_JWT_SECRET`
- **THEN** `exp - iat` SHALL equal `settings.jwt_access_ttl_seconds`
  (default 3600 s)

### Requirement: Lockout policy

The adapter SHALL track failed authentication attempts in
`auth_local_users.verification_attempts` and SHALL reject further
attempts for one hour once the counter reaches five within a one-hour
rolling window. A successful authentication SHALL reset the counter to
zero. The lockout error SHALL include the seconds remaining until the
window expires.

#### Scenario: Sixth failed attempt is locked

- **WHEN** five `authenticate(...)` calls with the wrong password are
  made within ten minutes, then a sixth call arrives with the **correct**
  password
- **THEN** the sixth call SHALL still raise the lockout error and SHALL
  NOT issue tokens, until the one-hour window elapses

### Requirement: Verification-code TTLs and resend rate-limit

Signup verification codes SHALL expire 15 minutes after issuance;
password-reset codes SHALL expire 10 minutes after issuance. The
adapter SHALL reject `resend_confirmation(...)` calls that arrive
within 60 seconds of the previous send for the same email
(per-email rate-limit).

#### Scenario: Expired signup code is rejected

- **WHEN** `confirm_signup(...)` is called with a code issued more than
  15 minutes earlier
- **THEN** the call SHALL raise the invalid-credentials error type

#### Scenario: Resend within 60 s is rate-limited

- **WHEN** `resend_confirmation(email=...)` has been called and a
  second `resend_confirmation` for the same email arrives 30 seconds
  later
- **THEN** the second call SHALL be rate-limited

### Requirement: `global_signout(...)` is idempotent and a no-op for refresh state

`global_signout(external_sub=...)` SHALL return `None` for any
`external_sub`, including unknown ones — there is no `auth_local_users`
state to clear because refresh-token rotation is not active in MVP
(per [`docs/06-security-model.md` §Refresh and revocation](../../../../docs/06-security-model.md#refresh-and-revocation),
local does not persist refresh tokens; the JWT itself is the only
revocation surface and access tokens expire by `exp`). The method
exists on the local adapter solely to honour the port contract and
keep the logout use case symmetric across adapters; when refresh-token
rotation lands post-MVP, the local adapter will gain an
`auth_local_refresh_tokens` table that this method will truncate.

#### Scenario: Logout against the local adapter succeeds

- **WHEN** `global_signout(external_sub="any")` is called
- **THEN** the method SHALL return `None` and SHALL NOT raise,
  regardless of whether `external_sub` exists in `auth_local_users`

### Requirement: `forgot_password(...)` silently no-ops for unknown emails

`forgot_password(email=...)` SHALL silently return success when the
supplied email is absent from `auth_local_users` (no row inserted, no
code generated, no SMTP send). This is the adapter-side half of the
enumeration-resistance contract — without it, the use case cannot
keep the HTTP response uniform.

#### Scenario: Unknown email yields a success result

- **WHEN** `forgot_password(email="missing@x.io")` is called and no
  row in `auth_local_users` matches
- **THEN** the method SHALL return a result whose shape matches the
  real-account reset and SHALL NOT raise, and Mailpit SHALL NOT
  receive any message

### Requirement: `update_active_tenant` patches `attributes`

`update_active_tenant(external_sub, tenant_id)` SHALL update the JSONB
column `auth_local_users.attributes` so that
`attributes['custom:active_tenant']` equals the supplied `tenant_id`.
A subsequent `authenticate(...)` SHALL emit a JWT whose
`custom:active_tenant` claim matches.

#### Scenario: Updated tenant appears in the next token

- **WHEN** `update_active_tenant(user.external_sub, "tenant-x")` is
  called and the user logs in again
- **THEN** the new access token's `custom:active_tenant` claim SHALL
  equal `"tenant-x"`
