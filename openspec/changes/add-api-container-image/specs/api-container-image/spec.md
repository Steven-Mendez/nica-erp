## ADDED Requirements

### Requirement: Multistage Dockerfile builds a `linux/amd64` runtime image

`apps/api/Dockerfile` SHALL declare two stages. The `builder` stage
SHALL use `python:3.12-slim` and SHALL install `uv` via
`pip install --no-cache-dir uv`, copy `pyproject.toml`, `uv.lock`,
`README.md`, and `src/` into `/app`, and run
`uv sync --frozen --no-dev --no-install-project` followed by
`uv pip install --no-deps .`. The `runtime` stage SHALL use
`python:3.12-slim`, SHALL copy `/app/.venv` and `/app/src` from
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

#### Scenario: WeasyPrint imports inside the container

- **WHEN** `docker run --entrypoint python <image-tag> -c "import weasyprint; print(weasyprint.__version__)"`
  is executed
- **THEN** the command SHALL exit `0` and print a non-empty version
  string

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

#### Scenario: Test directories do not bloat the image

- **WHEN** `docker history --no-trunc <image-tag>` is inspected
- **THEN** no layer SHALL contain any file under `tests/` or
  `__pycache__/`
