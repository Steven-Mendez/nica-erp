## MODIFIED Requirements

### Requirement: Settings sourced from .env.local and environment

`bootstrap.settings.Settings` (pydantic-settings) SHALL read variables
from `.env.local` then `.env` (in that order) then the process
environment. It SHALL expose at least `app_env`, `version`, `git_sha`,
`database_url`, `alembic_database_url`, and `cors_allowed_origins`.
`git_sha` SHALL default to `os.environ.get("GIT_SHA", "unknown")` and
MUST NOT invoke `subprocess` at import time. When the API runs from
an image built by `scripts/build-and-push-image.sh`, the `GIT_SHA`
environment variable SHALL be present in the container environment
(baked in at image build time via the `ARG GIT_SHA` /
`ENV GIT_SHA=$GIT_SHA` pair) and SHALL equal the full
40-character commit SHA of the source tree used to build the image.
`get_settings()` SHALL be cached with
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
