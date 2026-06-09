## ADDED Requirements

### Requirement: API routes mount under `/api` when `app_env == "aws"`

`bootstrap.api.create_app()` SHALL mount every router under the
prefix `/api` when `settings.app_env == "aws"` and at the root
(`""`) otherwise. The CloudFront `/api/*` behavior forwards the
full path unchanged to the ALB, so the `/healthz` endpoint is
reachable at `/api/healthz` in AWS and at `/healthz` locally. The
ALB target group's health check path SHALL be `/api/healthz`
(matching the AWS-mode mount).

#### Scenario: AWS-mode healthz is reachable at /api/healthz

- **WHEN** the app is created with `APP_ENV=aws` and
  `GET /api/healthz` is invoked
- **THEN** the response SHALL be HTTP 200 with the standard healthz
  payload

#### Scenario: AWS-mode root healthz is not reachable

- **WHEN** the app is created with `APP_ENV=aws` and `GET /healthz`
  is invoked
- **THEN** the response SHALL be HTTP 404

#### Scenario: Local-mode healthz is reachable at /healthz

- **WHEN** the app is created with `APP_ENV=local` and `GET /healthz`
  is invoked
- **THEN** the response SHALL be HTTP 200 with the standard healthz
  payload

## MODIFIED Requirements

### Requirement: Local CORS for the Vite dev origin

`bootstrap.api.create_app()` SHALL register `CORSMiddleware` whenever
`settings.app_env` is any value other than `"aws"`, configured from
`settings.cors_allowed_origins` (default `["http://localhost:5173"]`).
The middleware MUST allow credentials, all methods, and all headers
from those origins.

When `settings.app_env == "aws"`, `bootstrap.api.create_app()`
SHALL NOT register `CORSMiddleware` at all. In that environment
`settings.cors_allowed_origins` SHALL default to the empty list
`[]`. CloudFront makes the SPA and the API share an origin so CORS
is unnecessary.

#### Scenario: Preflight from :5173 succeeds locally

- **WHEN** a browser sends an OPTIONS preflight from
  `http://localhost:5173` against `/healthz` and `app_env="local"`
- **THEN** the response SHALL include the matching
  `access-control-allow-origin` header

#### Scenario: AWS app skips CORS middleware entirely

- **WHEN** the FastAPI app is created with `APP_ENV=aws`
- **THEN** `app.user_middleware` SHALL NOT include any middleware
  whose class is `starlette.middleware.cors.CORSMiddleware`

#### Scenario: AWS app does not emit CORS headers

- **WHEN** an HTTP request is issued against the AWS-mode
  `/healthz` endpoint with `Origin: https://example.com`
- **THEN** the response SHALL NOT contain any
  `access-control-allow-origin` header

### Requirement: Settings sourced from .env.local and environment

`bootstrap.settings.Settings` (pydantic-settings) SHALL read variables
from `.env.local` then `.env` (in that order) then the process
environment. It SHALL expose at least `app_env`, `version`, `git_sha`,
`database_url`, `alembic_database_url`, and `cors_allowed_origins`.
`git_sha` SHALL default to `os.environ.get("GIT_SHA", "unknown")`
and MUST NOT invoke `subprocess` at import time. When the API runs
from an image built by `scripts/build-and-push-image.sh`, the
`GIT_SHA` environment variable SHALL be present in the container
environment (baked in at image build time via the `ARG GIT_SHA` /
`ENV GIT_SHA=$GIT_SHA` pair) and SHALL equal the full
40-character commit SHA of the source tree used to build the image.
The default value of `cors_allowed_origins` SHALL depend on
`app_env`: `["http://localhost:5173"]` when `app_env != "aws"`,
`[]` when `app_env == "aws"`. `get_settings()` SHALL be cached with
`functools.lru_cache(maxsize=1)`.

#### Scenario: get_settings returns the same instance

- **WHEN** `get_settings()` is called twice in the same process
- **THEN** both calls SHALL return the same object identity

#### Scenario: Default git_sha is "unknown"

- **WHEN** the `GIT_SHA` environment variable is unset
- **THEN** `Settings().git_sha` SHALL equal `"unknown"`

#### Scenario: Image-baked SHA reaches /healthz

- **WHEN** the API container built by
  `scripts/build-and-push-image.sh` from commit `<full-sha>` is run
  and `GET /healthz` is invoked
- **THEN** the JSON response SHALL include
  `"git_sha":"<full-sha>"`

#### Scenario: AWS mode default CORS origins is empty

- **WHEN** `Settings(APP_ENV="aws").cors_allowed_origins` is read
  with no explicit `CORS_ALLOWED_ORIGINS` env override
- **THEN** it SHALL equal `[]`

#### Scenario: Local mode default CORS origins includes Vite

- **WHEN** `Settings(APP_ENV="local").cors_allowed_origins` is read
  with no explicit `CORS_ALLOWED_ORIGINS` env override
- **THEN** it SHALL equal `["http://localhost:5173"]`
