## ADDED Requirements

### Requirement: `/v1/auth/*` router endpoints

The identity HTTP adapter SHALL register routes
`POST /v1/auth/register`, `POST /v1/auth/confirm-signup`,
`POST /v1/auth/resend-code`, `POST /v1/auth/login`,
`POST /v1/auth/refresh`, `POST /v1/auth/password/forgot`,
`POST /v1/auth/password/reset`, `POST /v1/auth/change-password`, and
`POST /v1/auth/logout`. Request and response bodies SHALL be Pydantic v2
models. All 4xx/5xx responses SHALL use
`Content-Type: application/problem+json` per
[`docs/08-api-conventions.md` §Errors](../../../../docs/08-api-conventions.md#errors--rfc-7807-problem-details)
with a stable `code` field.

#### Scenario: Register returns 201 with a generic body

- **WHEN** `POST /v1/auth/register` is invoked with `{"email":
  "yo@test.dev", "password": "Demo1234!@xy"}` against a clean local
  database
- **THEN** the response SHALL be HTTP 201 with a body that does not
  reveal whether the email pre-existed

#### Scenario: Login returns access and refresh tokens

- **WHEN** `POST /v1/auth/login` is invoked with valid credentials for
  a confirmed user
- **THEN** the response SHALL be HTTP 200 with a JSON body containing
  `access_token`, `refresh_token`, `id_token`, and `token_type =
  "Bearer"`

#### Scenario: Invalid credentials map to RFC-7807

- **WHEN** `POST /v1/auth/login` is invoked with a wrong password
- **THEN** the response SHALL be HTTP 401, `Content-Type:
  application/problem+json`, and the JSON body SHALL include `"code":
  "auth.invalid_credentials"`

### Requirement: `POST /v1/auth/logout` invalidates the server-side session

`POST /v1/auth/logout` SHALL require a valid JWT (any
`custom:active_tenant`, including empty) and SHALL invoke the `logout`
use case (which calls `IdentityProvider.global_signout(...)`). The
response SHALL be HTTP 204 on success with an empty body. Calling
logout twice in succession SHALL still return 204 — the route is
idempotent. The middleware allowlist for tenantless JWTs SHALL include
this route so a user without an active tenant can still log out.

#### Scenario: Authenticated logout returns 204

- **WHEN** `POST /v1/auth/logout` is invoked with a valid token
- **THEN** the response SHALL be HTTP 204 with no body, and the
  underlying `IdentityProvider.global_signout` SHALL have been called
  exactly once with the caller's `sub`

#### Scenario: Repeated logout still returns 204

- **WHEN** `POST /v1/auth/logout` is invoked twice in succession with
  the same token
- **THEN** both responses SHALL be HTTP 204 — neither SHALL surface a
  4xx or 5xx

#### Scenario: Unauthenticated logout is rejected with 401

- **WHEN** `POST /v1/auth/logout` is invoked without an
  `Authorization` header
- **THEN** the response SHALL be HTTP 401 with `code =
  "auth.invalid_credentials"`

### Requirement: `GET /v1/me` returns the authenticated profile

`GET /v1/me` SHALL require a valid JWT (any `custom:active_tenant`,
including empty) and SHALL return a JSON body containing `id`,
`email`, `display_name`, `locale`, `timezone`, `preferences`,
`active_tenant` (string or `null`). It MUST NOT return any password
hash, password reset code, or any field from `auth_local_users`.

#### Scenario: Authenticated `/me` returns the profile

- **WHEN** `GET /v1/me` is called with a valid `Authorization: Bearer
  <jwt>` for an active user
- **THEN** the response SHALL be HTTP 200 and the JSON body SHALL
  contain the user's `email` and `display_name` as stored in `users`

#### Scenario: Unauthenticated `/me` is rejected with 401

- **WHEN** `GET /v1/me` is called without an `Authorization` header
- **THEN** the response SHALL be HTTP 401 with `code =
  "auth.invalid_credentials"`

### Requirement: `PATCH /v1/me` updates editable profile fields

`PATCH /v1/me` SHALL accept partial updates of `display_name`,
`locale`, `timezone`, and `preferences`. It MUST NOT accept changes to
`email`, `external_sub`, `id`, `created_at`, or `updated_at`. On
success it SHALL return the updated profile and an HTTP 200.

#### Scenario: Patching `display_name` succeeds

- **WHEN** `PATCH /v1/me` is called with `{"display_name": "Alice"}`
  and a valid token
- **THEN** the response SHALL be HTTP 200 and a follow-up `GET /v1/me`
  SHALL return `"display_name": "Alice"`

#### Scenario: Patching `email` is rejected

- **WHEN** `PATCH /v1/me` is called with `{"email": "new@x.io"}`
- **THEN** the response SHALL be HTTP 422 with `code =
  "validation.request_invalid"`

### Requirement: Authentication middleware validates per `APP_ENV`

The application SHALL install an authentication middleware that reads
the `Authorization: Bearer <jwt>` header, validates the token per
`settings.app_env` (`local` → HS256 with `settings.local_jwt_secret`;
`aws` → RS256 via Cognito JWKS), extracts the claims `sub`, `email`,
and `custom:active_tenant`, and populates
`shared_kernel.adapters.context.CurrentUserContext`. On a missing or
invalid token the middleware SHALL return HTTP 401 with a problem
detail. The middleware SHALL be installed **after** `CORSMiddleware`.

#### Scenario: Valid HS256 token under `APP_ENV=local`

- **WHEN** a request with a valid HS256 JWT signed with
  `LOCAL_JWT_SECRET` reaches `GET /v1/me`
- **THEN** the middleware SHALL accept the token and the request handler
  SHALL observe `CurrentUserContext.get()` returning a populated
  `CurrentUser`

#### Scenario: Token signed with the wrong key is rejected

- **WHEN** a request carries an HS256 JWT signed with a key other than
  `LOCAL_JWT_SECRET` under `APP_ENV=local`
- **THEN** the response SHALL be HTTP 401 with `code =
  "auth.invalid_credentials"`

### Requirement: Unauthenticated allowlist

The middleware SHALL skip JWT validation for these path prefixes:
`POST /v1/auth/register`, `POST /v1/auth/confirm-signup`,
`POST /v1/auth/resend-code`, `POST /v1/auth/login`,
`POST /v1/auth/refresh`, `POST /v1/auth/password/forgot`,
`POST /v1/auth/password/reset`, `POST /v1/invitations/{token}/accept`,
`GET /healthz`, `GET /readyz`, `GET /docs`, `GET /openapi.json`. Every
other route SHALL require a valid JWT.

#### Scenario: `/healthz` is reachable without a token

- **WHEN** `GET /healthz` is called without an `Authorization` header
- **THEN** the response SHALL be HTTP 200 — not 401

#### Scenario: An unlisted route requires a token

- **WHEN** `GET /v1/me` is called without an `Authorization` header
- **THEN** the response SHALL be HTTP 401

### Requirement: Authenticated-without-tenant allowlist

The middleware SHALL allow only `GET /v1/me`, `PATCH /v1/me`,
`POST /v1/auth/logout`, and `POST /v1/tenants` to be reached when the
request's JWT is valid but its `custom:active_tenant` claim is empty
or absent. Every other authenticated route SHALL respond with HTTP 403
and `code = "tenant.required"`. (Sprint 03 implements the body of
`POST /v1/tenants`; sprint 02 ships only the route stub and the
allowlist entry. `POST /v1/auth/logout` is in this allowlist so a user
with no active tenant — e.g., after `email_verified=true` but before
the first tenant creation — can still revoke their refresh token.)

#### Scenario: Tenantless JWT can reach `/me`

- **WHEN** a JWT with empty `custom:active_tenant` is presented at
  `GET /v1/me`
- **THEN** the response SHALL be HTTP 200

#### Scenario: Tenantless JWT cannot reach an arbitrary route

- **WHEN** the same JWT is presented at `GET /v1/some-other-resource`
- **THEN** the response SHALL be HTTP 403 with `code =
  "tenant.required"`
