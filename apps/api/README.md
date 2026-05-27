# nica-erp — API

FastAPI backend for nica-erp. Source under `src/` (no wrapping package):
imports are `from bootstrap.X` / `from shared_kernel.X` / `from contexts.X`.

Tests live under `tests/{unit,integration,e2e}/` (auto-marked by folder via
`conftest.py`). Run from this directory:

```sh
uv sync                                # install deps
uv run pytest                          # all suites
uv run pytest -m unit                  # unit only
uv run alembic upgrade head            # apply migrations
uv run uvicorn bootstrap.api:app --reload
```

## Container image

`Dockerfile` ships a multistage build (Python 3.13 slim + WeasyPrint native
libraries baked in for sprint 05's PDF generation). The image is built and
pushed by `scripts/build-and-push-image.sh` (wrapped by `make build-image`);
the produced tag is written to `.deploy-image-tag` at repo root for the
deploy script to consume.

### `GIT_SHA` build-arg → env-var → `/healthz` contract

The Dockerfile declares:

```dockerfile
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA
```

`scripts/build-and-push-image.sh` passes
`--build-arg GIT_SHA=$(git rev-parse HEAD)` so the running container's
`GIT_SHA` environment variable equals the full 40-character commit SHA of
the source tree that built it. `bootstrap.settings.Settings.git_sha` reads
that env var (defaulting to `"unknown"` when unset, as in `make api`), and
the value is returned verbatim by `GET /healthz` as the `git_sha` field.
