## ADDED Requirements

### Requirement: Application factory and FastAPI mount

`bootstrap.api.create_app()` SHALL build and return a `FastAPI` instance
with `title="nica-erp"`, `version=settings.version`, and the default
OpenAPI docs at `/docs` and `/redoc`. A module-level `app = create_app()`
SHALL exist so that `uvicorn bootstrap.api:app` boots the API.

#### Scenario: Importing the module exposes a FastAPI app
- **WHEN** `from bootstrap.api import app` is executed
- **THEN** `app` SHALL be a `fastapi.FastAPI` instance

### Requirement: Local CORS for the Vite dev origin

The app SHALL register `CORSMiddleware` configured from
`settings.cors_allowed_origins` (default `["http://localhost:5173"]`).
The middleware MUST allow credentials, all methods, and all headers from
those origins.

#### Scenario: Preflight from :5173 succeeds locally
- **WHEN** a browser sends an OPTIONS preflight from
  `http://localhost:5173` against `/healthz`
- **THEN** the response SHALL include the matching
  `access-control-allow-origin` header

### Requirement: /healthz reports DB state and Alembic revision

`GET /healthz` SHALL execute a `SELECT 1` and a `SELECT version_num FROM
alembic_version` through a `UnitOfWork` (injected via `Depends(get_uow)`).
On success, it SHALL respond with JSON `{"status":"ok",
"version":<settings.version>, "git_sha":<settings.git_sha>, "db":"ok",
"alembic_revision":<revision-or-null>}` and HTTP 200.

#### Scenario: Healthz returns the active Alembic revision
- **WHEN** `GET /healthz` is called against an API whose database is on
  revision `0001_shared_kernel`
- **THEN** the JSON body SHALL include `"alembic_revision":
  "0001_shared_kernel"` and `"db": "ok"`

### Requirement: Settings sourced from .env.local and environment

`bootstrap.settings.Settings` (pydantic-settings) SHALL read variables
from `.env.local` then `.env` (in that order) then the process
environment. It SHALL expose at least `app_env`, `version`, `git_sha`,
`database_url`, `alembic_database_url`, and `cors_allowed_origins`.
`git_sha` SHALL default to `os.environ.get("GIT_SHA", "unknown")` and
MUST NOT invoke `subprocess` at import time. `get_settings()` SHALL be
cached with `functools.lru_cache(maxsize=1)`.

#### Scenario: get_settings returns the same instance
- **WHEN** `get_settings()` is called twice in the same process
- **THEN** both calls SHALL return the same object identity

#### Scenario: Default git_sha is "unknown"
- **WHEN** the `GIT_SHA` environment variable is unset
- **THEN** `Settings().git_sha` SHALL equal `"unknown"`

### Requirement: Async engine and session factory wired through DI

`bootstrap.db.get_engine()` SHALL build a single `AsyncEngine` against
`settings.database_url` with `pool_size=5`, `max_overflow=10`,
`pool_pre_ping=True`, and `pool_recycle=300`. `get_session_factory()`
SHALL build a single `async_sessionmaker(..., expire_on_commit=False)`.
`get_uow()` SHALL yield a fresh `SqlAlchemyUnitOfWork` per request.
Both factory accessors MUST be cached with `lru_cache`.

#### Scenario: Engine settings match the spec
- **WHEN** the engine returned by `get_engine()` is inspected
- **THEN** its pool size SHALL be `5`, max overflow `10`, pool recycle
  `300` seconds, and pool pre-ping SHALL be enabled
