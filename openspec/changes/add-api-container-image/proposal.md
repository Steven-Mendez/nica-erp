## Why

The ephemeral runtime stack from `add-aws-runtime-stack` (sprint 01)
needs a published container image in ECR before it can stand up an
ECS task. That image has to satisfy two future demands at the same
time: it has to boot the FastAPI app from `add-backend-walking-skeleton`
today, **and** it has to ship the native `weasyprint` system libraries
that [sprint 05](../../../docs/sprints/05-parties-and-sales.md)'s PDF
generation will need. The sprint doc
([sprint 01 §Production Dockerfile](../../../docs/sprints/01-aws-wiring-rolling-deploys.md))
chooses to install those libs from day one to avoid a second image
rebuild later, which means this change cannot be a minimal "hello
FastAPI" Dockerfile.

This change also introduces the `GIT_SHA` build-arg → env-var hand-off
that `/healthz` already returns from the local walking skeleton, so
the AWS-served `/healthz` reports the same field with the real commit
SHA instead of `unknown`.

## What Changes

- New `apps/api/Dockerfile` (multistage):
  - **builder** stage: `python:3.12-slim`, installs `uv`, copies
    `pyproject.toml`, `uv.lock`, `README.md`, `src/`, then
    `uv sync --frozen --no-dev --no-install-project` followed by
    `uv pip install --no-deps .` so the app is installed into a
    self-contained `.venv` without touching dev dependencies.
  - **runtime** stage: `python:3.12-slim`, installs the
    `weasyprint` native libs (`libcairo2`, `libgdk-pixbuf-2.0-0`,
    `libpangoft2-1.0-0`, `libpango-1.0-0`, `shared-mime-info`,
    `fonts-liberation`, `libffi-dev`), copies `.venv` and `src/`
    from the builder, sets `PATH=/app/.venv/bin:$PATH`, declares
    `ARG GIT_SHA=unknown` and `ENV GIT_SHA=$GIT_SHA`, `EXPOSE 8000`,
    and runs `uvicorn bootstrap.api:app --host 0.0.0.0 --port 8000`.
  - `apt-get` lists are pruned (`rm -rf /var/lib/apt/lists/*`) and
    `--no-install-recommends` is set so the runtime image stays as
    small as possible after the unavoidable weasyprint cost.
- New `apps/api/.dockerignore` excluding `.venv/`, `.pytest_cache/`,
  `__pycache__/`, `tests/`, `alembic/versions/__pycache__/`,
  `*.pyc`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, local env
  files (`.env`, `.env.local`, `.env.local.example` excluded too —
  the build never needs them) and the entire `apps/web/` tree.
- New `scripts/build-and-push-image.sh` (bash, `set -euo pipefail`):
  - Resolves the ECR repository URL from the bootstrap Terraform
    outputs (calls `terraform -chdir=infra/terraform/bootstrap output -raw ecr_repository_url`).
  - Computes `GIT_SHA=$(git rev-parse HEAD)` and `SHORT_SHA=$(git rev-parse --short HEAD)`;
    refuses to build if the working tree has uncommitted changes
    *unless* `ALLOW_DIRTY=1` is set (in which case the tag becomes
    `${SHORT_SHA}-dirty-<unix-ts>` and a warning is printed).
  - Logs in to ECR (`aws ecr get-login-password ... | docker login ...`).
  - Builds the image with
    `docker build --platform linux/amd64 --build-arg GIT_SHA=$GIT_SHA -t nica-erp:$SHORT_SHA apps/api/`,
    tags it as `${ecr_repo_url}:${SHORT_SHA}`, and pushes it.
  - Writes the final tag to `.deploy-image-tag` (gitignored) for the
    later deploy script to consume.
- New `Makefile` target `build-image` delegating to
  `scripts/build-and-push-image.sh`. The deploy/destroy surface
  (`make deploy`, etc.) lands in `add-deploy-destroy-automation`,
  not here.
- New apps/api `README.md` note (or refresh of an existing one) that
  documents the build-arg → env-var contract for `GIT_SHA`.

## Capabilities

### New Capabilities

- `api-container-image`: the multistage Dockerfile for `apps/api/`
  including the weasyprint runtime baseline, the `GIT_SHA` build-arg
  → env-var contract, and the `.dockerignore` that bounds the build
  context.
- `image-publish-pipeline`: the `build-and-push-image.sh` script,
  the `make build-image` Makefile target, and the rules around tag
  derivation, dirty-tree handling, and the `.deploy-image-tag`
  artifact that downstream deploy automation consumes.

### Modified Capabilities

- `api-bootstrap`: the existing requirement
  "Settings sourced from .env.local and environment" SHALL be
  augmented to require that `git_sha` reflects the real commit SHA
  baked into the image at build time when `app_env=aws`, rather
  than defaulting to `"unknown"`.

## Impact

- Affected code: new `apps/api/Dockerfile`, new
  `apps/api/.dockerignore`, new `scripts/build-and-push-image.sh`,
  new `Makefile` target `build-image`, and one gitignore line for
  `.deploy-image-tag` (added in `add-terraform-state-backend`).
- Affected APIs: the `git_sha` field in `GET /healthz` SHALL now
  report the real commit SHA when the API runs from a published
  image; the local `make api` path still reports the value of the
  `GIT_SHA` env var (default `unknown`).
- Dependencies: requires `docker` on the operator host (already
  required for `make local-up`); requires the bootstrap change
  (`add-terraform-state-backend`) to be applied so the ECR
  repository exists. No new Python or system runtime dependencies
  beyond the weasyprint libs listed above.
- Systems: pushes images of the size dictated by weasyprint (~200 MB
  uncompressed runtime layer). ECR storage is bounded by the
  5-image lifecycle from `add-terraform-state-backend`.
- Out of scope (intentionally): ECS task definitions, ALB target
  groups, anything that *runs* the image (`add-aws-runtime-stack`);
  the migration RunTask script that uses
  `entrypoint=["alembic","upgrade","head"]`
  (`add-deploy-destroy-automation`); CI publishing of the image
  ([ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md) — no CI/CD in
  the MVP).
