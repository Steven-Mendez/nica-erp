## ADDED Requirements

### Requirement: `APP_ENV` is a required setting with no default

`bootstrap.settings.Settings` SHALL declare `app_env` without a default
value. Instantiating `Settings` with `APP_ENV` unset or empty SHALL
raise a validation error at import time, so a misconfigured container
fails fast rather than silently falling back to the local identity
adapter in production.

#### Scenario: Empty `APP_ENV` fails fast

- **WHEN** `from bootstrap.settings import Settings; Settings()` is
  evaluated in a process where `APP_ENV` is unset
- **THEN** a validation error SHALL be raised

### Requirement: `build_identity_provider()` factory branches on `app_env`

`bootstrap.container.build_identity_provider()` SHALL return
`IdentityProviderLocal(...)` when `settings.app_env == "local"` and
`IdentityProviderCognito(boto3.client("cognito-idp",
region_name=settings.cognito_region),
user_pool_id=settings.cognito_user_pool_id,
app_client_id=settings.cognito_app_client_id)` when `settings.app_env
== "aws"`. Any other value SHALL raise `ValueError`.

#### Scenario: Local app env returns the local adapter

- **WHEN** `build_identity_provider()` is called with
  `settings.app_env == "local"`
- **THEN** the returned object SHALL be an `IdentityProviderLocal`

#### Scenario: AWS app env returns the Cognito adapter

- **WHEN** `build_identity_provider()` is called with
  `settings.app_env == "aws"` and the Cognito settings populated
- **THEN** the returned object SHALL be an `IdentityProviderCognito`

### Requirement: `build_email_sender()` factory branches on `app_env`

`bootstrap.container.build_email_sender()` SHALL return
`EmailSenderSmtp(host=settings.smtp_host, port=settings.smtp_port)`
when `settings.app_env == "local"` and `EmailSenderSes(client=boto3.client("ses",
region_name=settings.cognito_region),
from_address=settings.ses_from_address)` when `settings.app_env ==
"aws"` (SESv1 client per
[`docs/sprints/02-identity-and-rbac.md` §Wiring](../../../../docs/sprints/02-identity-and-rbac.md#wiring)).
Any other value SHALL raise `ValueError`.

#### Scenario: Local app env returns the SMTP adapter

- **WHEN** `build_email_sender()` is called with `settings.app_env ==
  "local"`
- **THEN** the returned object SHALL be an `EmailSenderSmtp`

### Requirement: Authentication middleware is installed after CORS

`bootstrap.api.create_app()` SHALL install `AuthMiddleware` **after**
`CORSMiddleware`. This ordering ensures that 401 responses still carry
the CORS headers required by the SPA running on
`http://localhost:5173` during local development.

#### Scenario: CORS headers survive a 401

- **WHEN** the SPA at `http://localhost:5173` sends a request to a
  protected endpoint without a valid token
- **THEN** the 401 response SHALL include the matching
  `access-control-allow-origin` header

### Requirement: Identity HTTP router is mounted under `/v1`

`create_app()` SHALL mount the router exported from
`contexts.identity.adapters.inbound.http.router` under the prefix
`/v1`. After mount, `GET /openapi.json` SHALL list the eight auth
routes and the two `/v1/me` routes.

#### Scenario: OpenAPI documents the auth routes

- **WHEN** `GET /openapi.json` is fetched from a running app
- **THEN** the `paths` object SHALL include
  `/v1/auth/register`, `/v1/auth/confirm-signup`,
  `/v1/auth/resend-code`, `/v1/auth/login`, `/v1/auth/refresh`,
  `/v1/auth/password/forgot`, `/v1/auth/password/reset`,
  `/v1/auth/change-password`, and `/v1/me`
