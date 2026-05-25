## Context

This is the project's first change, so everything is greenfield. The architectural
constraints originate from the docs published in `docs/` (especially
[`docs/sprints/00-walking-skeleton.md`](../../../docs/sprints/00-walking-skeleton.md)
and the ADRs under `docs/adr/`):

- Hexagonal layering with a strict domain → application → adapters → bootstrap
  flow; later contexts (sales, inventory, billing) will plug into the same
  shared kernel, so the shapes of `UnitOfWork`, `EventBus`, `OutboxWriter`
  are load-bearing from day one.
- Inter-context communication will happen through an outbox + publisher,
  never through the in-process `EventBus`, which is reserved for intra-context
  domain events.
- All AWS-side concerns (Terraform, ECR, RDS, CloudFront, SES) are deferred
  to sprint 01 ([ADR-0018](../../../docs/adr/0018-rolling-deploys.md));
  sprint 00 is local-only.
- No CI/CD ([ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md)); GitHub
  Actions runs lint + tests only.

## Goals / Non-Goals

**Goals:**

- A contributor can clone the repo and reach `curl /healthz` →
  `{"db":"ok","alembic_revision":"0001_shared_kernel", …}` in under five
  minutes with a single `make local-up && make migrate && make api`.
- The `shared_kernel` package exposes ports stable enough that sprint 02
  (identity), sprint 03 (tenants + RLS), and the outbox publisher can
  depend on them without breaking changes.
- The Alembic 0001 migration introduces every cross-cutting table with its
  final shape so that future migrations only need to add columns/policies,
  never backfill the existing rows.
- `import-linter` blocks any future PR that imports SQLAlchemy from
  `shared_kernel.domain` or from any context's `domain` package.
- Integration and e2e tests run against a real Postgres testcontainer with
  Alembic already applied — no mocks of the database.

**Non-Goals:**

- Row-level security policies on `tenants`, `users`, `outbox` — sprint 03.
- JWT auth, identity middleware, RBAC, populated `TenantContext` /
  `CurrentUserContext` — sprint 02.
- Outbox publisher process, worker-outbox / worker-notif / worker-audit
  Makefile targets — later sprints.
- Production-grade Dockerfile, ECS task definitions, ALB, RDS, CloudFront,
  Terraform modules — sprint 01.
- `--autogenerate` for Alembic; migrations are hand-written so that schema
  intent is reviewable.
- Frontend changes (a separate `walking-skeleton-frontend` change covers
  `apps/web/`).

## Decisions

### Two database URLs, two drivers
- `DATABASE_URL` uses `postgresql+asyncpg://…` — the FastAPI runtime is
  fully async.
- `ALEMBIC_DATABASE_URL` uses `postgresql+psycopg://…` — `alembic upgrade`
  runs synchronously and we want the standard `engine_from_config` path,
  not the async one. `alembic/env.py` falls back to deriving the psycopg
  URL from `DATABASE_URL` so most contributors can set just one variable.
- Alternative considered: a single async URL routed through
  `async_engine_from_config` in `env.py`. Rejected — Alembic's async story
  is heavier than psycopg-sync, and migrations are not on the hot path.

### Hand-written migrations, no SQLAlchemy metadata at the migration layer
- `alembic/env.py` sets `target_metadata = None` (a comment makes this
  explicit). Contributors write the migration body, not `--autogenerate`
  diff output.
- Rationale: this is a regulated-data ERP; we want every column,
  constraint, and index named in code review, and we want `outbox` /
  `idempotency_keys` / `processed_events` to have their final, opinionated
  shape from the start.

### Outbox shape from day one (incl. `tenant_id`)
- `outbox.tenant_id UUID NOT NULL` ships in 0001 even though no
  multi-tenancy logic exists yet. When sprint 03 adds RLS, no rows need to
  be backfilled.
- Partial index `idx_outbox_unpublished ON outbox (occurred_at) WHERE
  published_at IS NULL` makes the publisher's polling query cheap.
- `OutboxWriterSqlAlchemy.append()` takes its session from the active
  `SqlAlchemyUnitOfWork.current_session` rather than from an injected
  `AsyncSession`, so the row physically commits inside the same
  transaction as the aggregate change. This is the whole point of the
  outbox pattern; making it easy to do right makes it hard to get wrong.

### `current_session` exposed on the UoW, not on a ContextVar
- Alternative considered: stash the active session on a `ContextVar` so
  any adapter can call `session_var.get()`. Rejected — that hides the
  dependency and makes test setup harder. Adapters that need the session
  receive the UoW explicitly.

### `Money` as `Decimal` + 3-letter ISO uppercase string
- `__post_init__` coerces non-`Decimal` amounts via `Decimal(str(...))`
  (string-conversion avoids float-precision artifacts), validates currency
  format, and raises `CurrencyMismatchError` (a `ValueError` subclass) on
  mixed-currency arithmetic so callers can catch either type.

### pytest auto-markers by location
- `conftest.py` walks `item.path` and applies `unit` / `integration` /
  `e2e` markers based on directory naming (`domain/`, `application/`,
  `adapters/`, `tests/{unit,integration,contract,e2e}/`).
- Rationale: contributors never need to write `@pytest.mark.integration`
  by hand, and `pytest -m unit` in CI works without manual upkeep.

### Single session-scoped Postgres testcontainer
- `_run_migrations` is `autouse=True` at session scope and runs
  `alembic upgrade head` once. All integration + e2e tests share the same
  container and the same schema; per-test isolation comes from
  transactional rollback inside `SqlAlchemyUnitOfWork.begin()`.
- Alternative considered: container-per-test. Rejected — startup cost
  (~3-5 s) would dominate the suite.

### `import-linter` over hand-rolled CI grep
- A formal contract is easier to evolve (later sprints add contracts for
  cross-context imports) and produces a stable, structured error when
  someone breaks it.

### CORS only on local
- Production places the SPA and API behind the same CloudFront origin
  ([ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md)), so CORS
  becomes a no-op. We still ship the middleware now because Vite at
  `:5173` would otherwise be blocked from `:8000`.

## Risks / Trade-offs

- **Risk**: `outbox.tenant_id NOT NULL` from 0001 forces every writer to
  pass a tenant id even before sprint 02/03 populate the context. →
  **Mitigation**: there is no writer yet; the first writer arrives only
  after `TenantContext` is wired up.
- **Risk**: `system_info` singleton makes a future need for multiple
  rows awkward. → **Mitigation**: by design — `system_info` exists so
  `/healthz` can `SELECT 1` against a real, deterministic row, not to
  store arbitrary key/value pairs.
- **Risk**: testcontainers fails on machines without Docker, breaking
  `make test`. → **Mitigation**: `pytest -m unit` (which is what CI
  runs) does not touch the container; integration/e2e are opt-in
  locally.
- **Risk**: `--autogenerate` is unavailable because `target_metadata =
  None`. → **Trade-off**: accepted; hand-written migrations are the
  policy.
- **Risk**: `lucide-react@1.16.0` and friends in `apps/web/package.json`
  (not in scope here) drift from the API CI lifecycle — out of scope
  for this backend+infra change.

## Migration Plan

- This is the bootstrap change; there is no prior state to roll back to.
- Deploy: `make local-up && make migrate` brings the stack from zero to
  the post-0001 schema. The `downgrade()` of 0001 drops all six tables
  + the partial index, so `make migrate-down` returns to an empty
  database.
- Rollback: `git revert` the change directory + `make migrate-down`.

## Open Questions

- (none for sprint 00 — frozen by the docs in `docs/sprints/00-…` and
  the relevant ADRs)
