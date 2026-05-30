## ADDED Requirements

### Requirement: `IdentityProviderCognito` calls cognito-idp exclusively

The `IdentityProviderCognito` adapter SHALL implement every method of
`IdentityProvider` by invoking the corresponding `cognito-idp` API:
`SignUp`, `ConfirmSignUp`, `ResendConfirmationCode`, `InitiateAuth`
(with `AuthFlow="USER_PASSWORD_AUTH"` for `authenticate` and
`AuthFlow="REFRESH_TOKEN_AUTH"` for `refresh`), `GlobalSignOut`,
`ForgotPassword`, `ConfirmForgotPassword`, `ChangePassword`,
`AdminUpdateUserAttributes`, `AdminGetUser`. The adapter MUST NOT call
any cognito-idp method outside that allow-list (in particular: no
`AdminDeleteUser`, no `AdminSetUserPassword`). The adapter SHALL live
in `contexts.identity.adapters.outbound.identity_provider.cognito`.

#### Scenario: Adapter is selected only when `APP_ENV=aws`

- **WHEN** `bootstrap.container.build_identity_provider()` is called
  with `settings.app_env == "aws"`
- **THEN** the returned instance SHALL be `IdentityProviderCognito`

### Requirement: JWKS cache with 24 h TTL, refresh-on-miss, stale-on-error

`verify_token(...)` SHALL validate the supplied JWT against the
Cognito User Pool's JWKS document fetched from
`https://cognito-idp.<region>.amazonaws.com/<user_pool_id>/.well-known/jwks.json`.
The fetched JWKS SHALL be cached in process memory with a 24-hour
TTL. On cache miss the adapter SHALL fetch under a lock so concurrent
requests do not stampede. If the JWKS endpoint returns an error and a
**stale** cache is available, the adapter SHALL use the stale cache
rather than reject the request. If no cache is available and the fetch
fails, the adapter SHALL raise the invalid-credentials error type.

#### Scenario: First request fetches and caches JWKS

- **WHEN** `verify_token(...)` is called with the cache empty
- **THEN** the adapter SHALL perform exactly one outbound HTTP call to
  the JWKS endpoint and the cache SHALL be populated for subsequent
  calls within the 24 h TTL

#### Scenario: Stale cache used on transient JWKS error

- **WHEN** the cache is populated but expired, the JWKS HTTP fetch
  returns a 5xx, and a `verify_token(...)` call arrives
- **THEN** the adapter SHALL validate against the **stale** cache and
  SHALL NOT raise

#### Scenario: No cache and error fails closed

- **WHEN** the cache is empty and the JWKS HTTP fetch returns a 5xx
- **THEN** `verify_token(...)` SHALL raise the invalid-credentials
  error type (HTTP 401)

### Requirement: RS256 signature, audience, issuer, and expiry enforcement

`verify_token(...)` SHALL verify the RS256 signature against the JWKS
key whose `kid` matches the JWT header's `kid`. It SHALL also enforce
`aud == settings.cognito_app_client_id`, `iss ==
f"https://cognito-idp.<region>.amazonaws.com/<user_pool_id>"`, and
`exp > now()`. An expired token SHALL surface as
`auth.token_expired`; any other validation failure SHALL surface as
`auth.invalid_credentials`.

#### Scenario: Expired token raises the typed error

- **WHEN** `verify_token(jwt)` is called with a token whose `exp` is
  in the past
- **THEN** the adapter SHALL raise the error type that the HTTP layer
  maps to HTTP 401 with `code = "auth.token_expired"`

### Requirement: `register(...)` returns a generic outcome on `UsernameExistsException`

The adapter SHALL NOT propagate `UsernameExistsException` raised by
`cognito-idp.SignUp` to the use case. Instead it SHALL return the same
shape as a successful registration, so the use case can collapse both
branches into a single enumeration-resistant response.

#### Scenario: Pre-existing email yields a success-shaped result

- **WHEN** `register(email="taken@x.io", password=valid)` is called
  and `cognito-idp.SignUp` raises `UsernameExistsException`
- **THEN** the adapter SHALL return a result whose shape matches a
  fresh-email registration (no exception leaks to the use case)

### Requirement: `forgot_password(...)` swallows `UserNotFoundException`

The adapter SHALL NOT propagate `UserNotFoundException` raised by
`cognito-idp.ForgotPassword` to the use case. It SHALL return the
same shape as a real-account `ForgotPassword` invocation. This is the
adapter-side half of the enumeration-resistance contract — without
it, the use case cannot keep the HTTP response uniform between
existing and non-existing accounts (a `UserNotFoundException` would
otherwise surface as a 5xx that leaks the email's existence).
`InvalidParameterException` and other genuine client errors SHALL
continue to propagate.

#### Scenario: Non-existing email yields a success-shaped result

- **WHEN** `forgot_password(email="missing@x.io")` is called and
  `cognito-idp.ForgotPassword` raises `UserNotFoundException`
- **THEN** the adapter SHALL return a result whose shape matches a
  real-account reset (no exception leaks to the use case)

#### Scenario: Genuinely invalid input still raises

- **WHEN** `forgot_password(email="not-an-email")` is called and
  `cognito-idp.ForgotPassword` raises `InvalidParameterException`
- **THEN** the adapter SHALL propagate the exception so the HTTP layer
  surfaces a 422 with `code = "validation.request_invalid"`

### Requirement: `global_signout(...)` is idempotent against Cognito

`global_signout(external_sub=...)` SHALL call
`cognito-idp.GlobalSignOut` with the user's `Username` (Cognito uses
`sub` as `Username` when emails are the alias). The adapter SHALL
swallow `UserNotFoundException` and `NotAuthorizedException` (the
user already has no active session) and return `None` in those
cases — the logout use case is idempotent and the HTTP layer always
returns 204.

#### Scenario: Successful global signout

- **WHEN** `global_signout(external_sub="abc-123")` is called and
  `cognito-idp.GlobalSignOut` returns 200
- **THEN** the adapter SHALL return `None`

#### Scenario: Already-signed-out user does not raise

- **WHEN** `global_signout(external_sub="abc-123")` is called and
  `cognito-idp.GlobalSignOut` raises `NotAuthorizedException`
- **THEN** the adapter SHALL return `None` (the logout is treated as
  already complete)
