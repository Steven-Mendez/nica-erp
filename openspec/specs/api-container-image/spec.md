# api-container-image Specification

## Purpose
TBD - created by archiving change add-api-container-image. Update Purpose after archive.
## Requirements
### Requirement: Multistage Dockerfile builds a `linux/amd64` runtime image

`apps/api/Dockerfile` SHALL declare two stages. The `builder` stage
SHALL use `python:3.13-slim` (matching `apps/api/pyproject.toml`'s
`requires-python = ">=3.13,<3.14"`) and SHALL install `uv` via
`pip install --no-cache-dir uv`, copy `pyproject.toml`, `uv.lock`,
`README.md`, and `src/` into `/app`, and run
`uv sync --frozen --no-dev --no-install-project` followed by
`uv pip install --no-deps .`. The `runtime` stage SHALL use
`python:3.13-slim`, SHALL copy `/app/.venv` and `/app/src` from
`builder`, and SHALL set `PATH="/app/.venv/bin:$PATH"`. The runtime
stage SHALL `EXPOSE 8000` and SHALL declare
`CMD ["uvicorn","bootstrap.api:app","--host","0.0.0.0","--port","8000"]`.

#### Scenario: Built image boots uvicorn

- **WHEN** the image is run with
  `docker run -e DATABASE_URL=... -p 8000:8000 <image-tag>`
- **THEN** the container SHALL listen on port `8000` and `GET /healthz`
  SHALL return HTTP 200 once the database is reachable

### Requirement: WeasyPrint native libraries are installed in the runtime stage

The runtime stage SHALL install via
`apt-get install -y --no-install-recommends` the following packages:
`libcairo2`, `libgdk-pixbuf-2.0-0`, `libpangoft2-1.0-0`,
`libpango-1.0-0`, `shared-mime-info`, `fonts-liberation`,
`libffi-dev`. The same `RUN` instruction SHALL conclude with
`rm -rf /var/lib/apt/lists/*` so apt cache does not persist in the
image layer.

The Python `weasyprint` package itself is not added until
[sprint 05](../../../docs/sprints/05-parties-and-sales.md);
sprint 01 commits only to having the *native* libraries already
present so adding the Python dependency later is a small `uv sync`
diff and not an apt rebuild.

#### Scenario: WeasyPrint native libraries are present

- **WHEN** `docker run --rm --entrypoint dpkg <image-tag> -s libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libpangoft2-1.0-0 shared-mime-info fonts-liberation libffi-dev`
  is executed
- **THEN** the command SHALL exit `0` and SHALL report
  `Status: install ok installed` for each package

### Requirement: Alembic env and revisions ship inside the runtime image

The runtime stage SHALL `COPY` `alembic.ini` and the `alembic/`
directory (containing `env.py` and `versions/`) into `/app/` so
the same image can serve `uvicorn` and run
`alembic upgrade head` without a second image or a separate
build context. This is what
`add-deploy-destroy-automation`'s migration RunTask invokes via
the `nica-erp-migrate` ECS task definition's command override
`["alembic","upgrade","head"]`.

#### Scenario: Alembic CLI runs against the built image

- **WHEN** `docker run --rm --entrypoint alembic <image-tag> heads`
  is executed with `DATABASE_URL` / `ALEMBIC_DATABASE_URL` set
- **THEN** the command SHALL exit `0` and print the current head
  revision rather than failing with `FileNotFoundError: alembic.ini`

### Requirement: `GIT_SHA` build arg becomes the runtime environment variable

The runtime stage SHALL declare `ARG GIT_SHA=unknown` followed by
`ENV GIT_SHA=$GIT_SHA`. When `docker build --build-arg GIT_SHA=<sha>`
is supplied, the running container's environment SHALL expose
`GIT_SHA=<sha>` and `bootstrap.settings.Settings().git_sha` SHALL
return that value.

#### Scenario: /healthz reports the baked-in SHA

- **WHEN** the image is built with `--build-arg GIT_SHA=abcdef1234`
  and run, and `GET /healthz` is invoked
- **THEN** the JSON response SHALL include
  `"git_sha":"abcdef1234"`

### Requirement: Dockerfile build context is bounded by `.dockerignore`

`apps/api/.dockerignore` SHALL exclude at minimum: `.venv/`,
`__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`,
`.ruff_cache/`, `.coverage`, `tests/`,
`alembic/versions/__pycache__/`, `.env`, `.env.local`, and
`.env.local.example`. The repo-root build context for the API
image SHALL NOT include `apps/web/` (excluded via
`apps/api/.dockerignore` because the Dockerfile is invoked with
`docker build apps/api/`).

#### Scenario: Project test directories do not bloat the image

- **WHEN** `docker run --rm --entrypoint sh <image-tag> -c 'ls /app/tests 2>&1'`
  is executed
- **THEN** the output SHALL contain `No such file or directory` (the
  project's `tests/` SHALL NOT be present in the image; third-party
  package test directories that live inside `.venv/lib/.../site-packages/`
  are out of scope for this check)

