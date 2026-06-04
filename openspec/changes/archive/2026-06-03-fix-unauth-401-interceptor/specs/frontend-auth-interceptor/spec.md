## ADDED Requirements

### Requirement: The auth interceptor wraps every SPA fetch with single-retry refresh

The frontend SHALL route all API requests through a single
`fetchWithAuth` wrapper in `apps/web/src/api/interceptor.ts`. The
wrapper SHALL:

- Attach `Authorization: Bearer <access_token>` to the outgoing
  request when the in-memory token store holds an access token, and
  attach nothing when the store is empty.
- On a 200-class or 4xx-class response other than 401, return the
  response to the caller unchanged.
- On a 401 *for a request that carried a bearer*: attempt
  `POST /v1/auth/refresh` exactly once (deduplicated across
  concurrent callers), retry the original request exactly once with
  the new bearer if refresh succeeded, and call `handleAuthLost()`
  (clearing the token store and invoking the registered
  `onAuthLost` callback) if either the refresh or the retry returns
  401.
- On a 401 *for a request that did not carry a bearer*: return the
  401 response to the caller unchanged. The wrapper MUST NOT
  attempt a refresh and MUST NOT invoke `handleAuthLost` for this
  case.

The discriminator between the two 401 branches MUST be carried on
the wrapping init (a `__bearerAttached?: boolean` flag set by
`attachAuth` when, and only when, the `Authorization` header was
added). Other side channels (request URL pattern matching,
endpoint-specific opt-outs) MUST NOT be used.

#### Scenario: 401 with no bearer is a passthrough error

- **GIVEN** the in-memory access token store is empty (operator is
  on `/confirm` or `/reset-password` and has not signed in)
- **AND** the caller invokes `fetchWithAuth` against an endpoint
  whose response is 401 (e.g. `POST /v1/auth/confirm-signup` with a
  wrong OTP)
- **WHEN** `fetchWithAuth` receives the 401
- **THEN** the wrapper returns the 401 `Response` to the caller
  without attempting a refresh
- **AND** the registered `onAuthLost` callback is NOT invoked
- **AND** the SPA does NOT navigate to `/login`

#### Scenario: 401 with a bearer triggers single refresh + retry

- **GIVEN** the in-memory access token store holds an access token
  (operator is authenticated)
- **AND** a refresh token is also available
- **WHEN** the original request returns 401 and the subsequent
  refresh succeeds with new tokens
- **THEN** `fetchWithAuth` retries the original request once with
  the new bearer
- **AND** returns the retried response to the caller
- **AND** `onAuthLost` is NOT invoked when the retry succeeds

#### Scenario: 401 with a bearer + refresh failure fires auth-lost

- **GIVEN** the in-memory access token store holds an access token
- **AND** the refresh call returns a non-2xx response (or no
  refresh token is in store)
- **WHEN** `fetchWithAuth` exhausts its single-retry budget without
  recovering
- **THEN** `handleAuthLost()` is invoked: the token store is
  cleared and the registered `onAuthLost` callback fires
- **AND** the original 401 response is returned to the caller

#### Scenario: Wrong OTP on /confirm renders the inline alert and stays on the route

- **GIVEN** the operator is on `/confirm` and has not signed in
- **WHEN** they submit a wrong OTP and the backend returns 401
- **THEN** the SPA stays on `/confirm`
- **AND** `<FormErrorAlert />` renders the inline Spanish copy from
  the `messageForProblem` registry
- **AND** the SPA does NOT navigate to `/login`

#### Scenario: Used password-reset token renders the inline alert and stays on /reset-password

- **GIVEN** the operator is on `/reset-password` with a token that
  was already used to reset the password
- **WHEN** they submit the form and the backend returns 401 with
  `code: "auth.reset_token_used"`
- **THEN** the SPA stays on `/reset-password`
- **AND** the inline alert renders the Spanish copy from the
  `messageForProblem` registry
- **AND** the SPA does NOT navigate to `/login`

### Requirement: The interceptor is the single fetch wrapper for the SPA

Endpoints exposed by `apps/web/src/features/*/api/endpoints.ts` SHALL route through `fetchWithAuth`. They MUST NOT call `rawFetch` directly to opt out of the auth wrapper, except for the internal refresh call inside `tryRefresh` (and the boot-time recovery in `bootRefresh`), which MUST use `rawFetch` to avoid recursion.

This rule preserves a single code path for cross-cutting concerns
(authentication, telemetry, future tracing) and prevents the
"unauthenticated endpoint" knowledge from leaking into every
endpoint definition.

#### Scenario: Auth endpoints continue to flow through fetchWithAuth

- **GIVEN** any of `register`, `confirmSignup`, `resendCode`,
  `login`, `forgotPassword`, `resetPassword` in
  `apps/web/src/features/auth/api/endpoints.ts`
- **WHEN** the endpoint is invoked
- **THEN** the call path is `api.POST` (openapi-fetch) →
  `fetchWithAuth`, never `rawFetch` directly
