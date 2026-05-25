# developer-toolchain Specification

## Purpose
TBD - created by archiving change add-backend-walking-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Makefile exposes the sprint-00 developer workflow

The root `Makefile` SHALL declare phony targets `help`, `doctor`,
`install`, `hooks`, `local-up`, `local-down`, `api`, `migrate`,
`migrate-down`, `makemigration`, `makemigration-auto`, `test`, `lint`,
and `format`. `help` SHALL be the default goal and SHALL print the
target list parsed from `## ` comments. Recipes MUST be indented with a
literal tab character.

#### Scenario: Running `make` with no target prints help
- **WHEN** a developer runs `make` in the repo root
- **THEN** the help summary SHALL list each documented target

#### Scenario: `make api` exports GIT_SHA
- **WHEN** `make api` is run inside a git checkout
- **THEN** the spawned uvicorn process SHALL see a non-empty
  `GIT_SHA` environment variable derived from `git rev-parse --short
  HEAD`

### Requirement: Pre-commit hooks gate lint, types, and contracts

`.pre-commit-config.yaml` at the repo root SHALL declare local hooks
that run `ruff format`, `ruff check --fix`, `mypy`, and `lint-imports`
against Python files. Hooks MUST execute with the API's `uv`
environment.

#### Scenario: `pre-commit run --all-files` passes on a clean tree
- **WHEN** all Python hooks run against the committed codebase
- **THEN** every hook SHALL exit with code 0

### Requirement: GitHub Actions runs lint/type/test on PRs touching apps/api

`.github/workflows/api-checks.yml` SHALL trigger on pushes to `main` and
on pull requests whose changes include `apps/api/**` or the workflow
file itself. It SHALL run, in order: `uv sync --frozen`, `ruff check`,
`ruff format --check`, `mypy`, `lint-imports`, and `pytest -m unit`.
The job SHALL NOT perform deployments.

#### Scenario: Workflow runs only relevant checks
- **WHEN** a pull request modifies only `apps/api/src/**`
- **THEN** the `api-checks` workflow SHALL execute and SHALL NOT run
  any deploy or release step

### Requirement: import-linter contract protects domain purity

`apps/api/.importlinter` SHALL declare a `forbidden`-type contract named
`Domain free of SQLAlchemy/FastAPI/boto3`. Its `source_modules` SHALL
cover `shared_kernel.domain` and each `contexts.<context>.domain`
package; its `forbidden_modules` SHALL cover `sqlalchemy`, `fastapi`,
`boto3`, `shared_kernel.adapters`, and each
`contexts.<context>.application` and `contexts.<context>.adapters`
package. Each new context introduced in a later sprint MUST extend both
lists in the same PR that creates the context's packages.

#### Scenario: Contract is kept on the current codebase
- **WHEN** `uv run lint-imports` is executed in `apps/api/`
- **THEN** the contract SHALL report `KEPT`

#### Scenario: A new context is introduced
- **WHEN** a PR adds `contexts.<new_context>.domain`,
  `contexts.<new_context>.application`, and/or
  `contexts.<new_context>.adapters`
- **THEN** the same PR SHALL extend `source_modules` with
  `contexts.<new_context>.domain` and `forbidden_modules` with
  `contexts.<new_context>.application` and
  `contexts.<new_context>.adapters`

### Requirement: pytest configuration and auto-markers

`apps/api/pyproject.toml` SHALL enable `asyncio_mode = "auto"`, declare
`pythonpath = ["src"]`, set `testpaths = ["tests"]`,
`python_files = ["test_*.py"]`, and register markers `unit`,
`integration`, `contract`, `e2e`. All tests SHALL live under
`apps/api/tests/` (not co-located with production code in `src/`). The
`apps/api/conftest.py` SHALL inspect each test's path and add the marker
matching its top-level folder under `tests/` (`tests/unit/` → `unit`;
`tests/integration/` → `integration`; `tests/contract/` → `contract`;
`tests/e2e/` → `e2e`). Sub-folder layout under each level MUST mirror
the `src/` package layout (e.g. `src/shared_kernel/domain/money.py` is
tested by `tests/unit/shared_kernel/domain/test_money.py`).

#### Scenario: Tests under tests/integration/ collect under -m integration
- **WHEN** `pytest -m integration` runs from `apps/api/`
- **THEN** every test located under `tests/integration/` SHALL be
  selected and no test outside that folder SHALL be selected

#### Scenario: Unit tests run without Docker
- **WHEN** `pytest -m unit` runs on a host without Docker
- **THEN** the suite SHALL pass without attempting to start any
  testcontainer

#### Scenario: No tests are co-located with production code
- **WHEN** `find apps/api/src -name "test_*.py" -o -name "*_test.py"`
  is executed
- **THEN** the command SHALL produce no output (tests live exclusively
  under `apps/api/tests/`)

### Requirement: Shared Postgres testcontainer for integration and e2e

The root `conftest.py` of `apps/api/` SHALL define a session-scoped
`postgres_container` fixture (image `postgres:17-alpine`) and a
session-scoped, `autouse=True` fixture that runs `alembic upgrade head`
against that container exactly once before integration/e2e tests
execute. A `session_factory` fixture SHALL yield an
`async_sessionmaker` bound to the testcontainer for use by adapter and
e2e tests.

#### Scenario: All integration + e2e tests share one container
- **WHEN** `pytest -m "integration or e2e"` runs locally
- **THEN** exactly one `postgres:17-alpine` container SHALL start for
  the duration of the suite

