# syntax=docker/dockerfile:1.7
#
# apps/api/Dockerfile — multistage build for the nica-erp FastAPI image.
#
# Build context: `apps/api/` (invoked as `docker build apps/api/`). Tags are
# managed by `scripts/build-and-push-image.sh`, which passes the full
# 40-character commit SHA via `--build-arg GIT_SHA=<sha>` so the runtime
# stage can expose it as the `GIT_SHA` environment variable for /healthz.

# ---- builder ----------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-install-project \
 && uv pip install --no-deps .

# ---- runtime ----------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# WeasyPrint native dependencies, installed now (sprint 01) so sprint 05's
# PDF invoice generation does not require an image rebuild.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libpangoft2-1.0-0 \
        libpango-1.0-0 \
        shared-mime-info \
        fonts-liberation \
        libffi-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src   /app/src

# alembic env + revisions live alongside the application source so the
# migration RunTask (add-deploy-destroy-automation) can invoke
# `alembic upgrade head` against the same image.
COPY alembic.ini ./alembic.ini
COPY alembic     ./alembic

ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

EXPOSE 8000

CMD ["uvicorn", "bootstrap.api:app", "--host", "0.0.0.0", "--port", "8000"]
