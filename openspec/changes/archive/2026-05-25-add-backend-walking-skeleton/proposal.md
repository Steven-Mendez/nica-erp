## Why

The repository needs a runnable end-to-end foundation before any business
capability can be built: a typed Python project that starts a real FastAPI
process, a Postgres instance reachable from that process, and a single
migration that creates the cross-cutting tables every later context relies on
(`outbox`, `processed_events`, `idempotency_keys`, `tenants`, `users`,
`system_info`). Without this skeleton, contributors cannot validate domain
code against a real database, integration/e2e tests cannot run, and later
sprints have no place to hook into. Doing it once, deliberately, fixes the
boundaries (domain-purity, async UoW, outbox-shaped writes) that are expensive
to retrofit later.

## What Changes

- New Python project under `apps/api/` using `uv`, Python 3.13, FastAPI,
  pydantic-settings, structlog, SQLAlchemy 2 (asyncio), asyncpg, psycopg
  (sync driver for Alembic), Alembic 1.13, structured for hexagonal layering
  (`bootstrap/`, `shared_kernel/{domain,application,adapters}`, `contexts/`).
- New `/healthz` endpoint that reads the active Alembic revision through a
  `UnitOfWork` so a single HTTP call proves the API↔DB↔migrations path.
- `shared_kernel.domain` ships `Entity`, `AggregateRoot`, `DomainEvent`,
  `ValueObject`, and `Money` (3-letter ISO currency, same-currency
  arithmetic, `CurrencyMismatchError`).
- `shared_kernel.application` ships the `UnitOfWork`, `Command`, `Query`,
  `EventBus` (+ `InProcessEventBus`) and `OutboxWriter` protocols — every
  later context depends on these signatures.
- `shared_kernel.adapters` ships `SqlAlchemyUnitOfWork`,
  `OutboxWriterSqlAlchemy` (joins the active UoW's session so aggregate and
  event commit atomically), `TenantContext`, `CurrentUserContext`
  (request-scoped `ContextVar`s populated by later sprints).
- Alembic migration `0001_shared_kernel` creates: `pgcrypto` + `citext`
  extensions; tables `tenants`, `users` (placeholder columns expanded
  later), `outbox` (full shape incl. `tenant_id NOT NULL` from day one,
  no RLS yet), `processed_events`, `idempotency_keys`, and `system_info`
  (singleton with `CHECK (id = 1)`); plus the partial index
  `idx_outbox_unpublished` on `occurred_at` filtered by
  `published_at IS NULL`.
- `import-linter` contract `domain-purity` enforces that
  `shared_kernel.domain` and every `contexts.<context>.domain` package
  import no `sqlalchemy`, `fastapi`, `boto3`,
  `shared_kernel.adapters`, nor any
  `contexts.<context>.{application,adapters}` package. Each new context
  added in later sprints extends both `source_modules` and
  `forbidden_modules` in the same PR.
- Local infrastructure via Docker Compose: Postgres 17-alpine (5432),
  LocalStack 3.7 (4566, services `s3,sqs,events,ssm`, init script creates
  S3 bucket `nica-erp-files`, SQS queues `notif-queue` + `audit-queue` and
  their DLQs, EventBridge bus `nica-erp`), Mailpit (1025/8025).
- Static toolchain: ruff (format + check), mypy strict, pytest +
  pytest-asyncio, httpx + respx, testcontainers[postgres],
  `pre-commit` hooks (ruff format, ruff check --fix, mypy, import-linter),
  GitHub Actions workflow `api-checks.yml` (lint + format + types +
  import-linter + unit tests on push/PR, no deploy).
- Makefile targets: `doctor`, `install`, `hooks`, `local-up`, `local-down`,
  `api`, `migrate`, `migrate-down`, `makemigration[-auto]`, `test`,
  `lint`, `format`. `make api` exports `GIT_SHA=$(git rev-parse --short HEAD)`
  so `/healthz` can echo it back.
- Pytest auto-marker by location (`domain/` and `application/` → `unit`;
  `adapters/` → `integration`; `tests/e2e/` → `e2e`) and a session-scoped
  Postgres `testcontainer` that runs `alembic upgrade head` once before
  integration and e2e suites share a session factory.

## Capabilities

### New Capabilities
- `shared-kernel-domain`: identity/value-object/event/aggregate primitives
  reused across every business context, plus `Money`.
- `shared-kernel-application`: transactional and messaging ports
  (`UnitOfWork`, `EventBus`, `OutboxWriter`, `Command`, `Query`) that every
  context calls into but never implements.
- `shared-kernel-adapters`: SQLAlchemy + ContextVar implementations of the
  ports above, including the outbox writer that piggybacks on the active
  UoW session for atomic aggregate↔event commits.
- `database-schema-bootstrap`: Alembic migration baseline (extensions,
  shared tables, outbox partial index, singleton `system_info`) that every
  later migration extends without backfilling.
- `api-bootstrap`: FastAPI application factory, CORS for the local Vite
  origin only, settings via pydantic-settings, `/healthz` endpoint that
  reports DB health and the live Alembic revision.
- `local-infrastructure`: Docker Compose stack (Postgres + LocalStack +
  Mailpit) and the LocalStack init script that pre-creates every AWS
  resource the app references by name.
- `developer-toolchain`: Makefile, pre-commit hooks, ruff/mypy/pytest
  configuration, import-linter contracts, GitHub Actions `api-checks`
  workflow, and the pytest auto-marker fixture wiring.

### Modified Capabilities
(none — this is the project's first change)

## Impact

- Affected code: new `apps/api/` Python package; new `docker/`,
  `.github/workflows/api-checks.yml`, `.pre-commit-config.yaml`,
  `Makefile`, `.env.local.example`.
- Affected APIs: introduces the public HTTP surface `GET /healthz`.
- Dependencies: pins FastAPI ≥0.115, SQLAlchemy 2.x, asyncpg ≥0.30,
  psycopg ≥3.2, Alembic ≥1.13, structlog 24.x, pydantic-settings 2.x;
  dev: ruff, mypy, pytest, httpx, respx, import-linter, pre-commit,
  testcontainers[postgres].
- Systems: requires a Postgres 17 instance and (locally) a running Docker
  daemon for `make local-up` and for the integration/e2e test
  containers. No AWS/Terraform impact (sprint 01).
- Out of scope (intentionally): row-level security policies (sprint 03),
  identity/JWT middleware (sprint 02), Terraform/ECR/RDS/CloudFront
  (sprint 01), domain workers (`worker-outbox`, `worker-audit`,
  `worker-notif`), production Dockerfile.
