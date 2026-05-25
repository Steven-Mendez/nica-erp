## 1. Repository and toolchain bootstrap

- [x] 1.1 Initialise the monorepo layout (`apps/api/`, `apps/web/` placeholder,
      `docker/`, `infra/terraform/` empty, `scripts/`, `docs/`,
      `.github/workflows/`) and seed `.editorconfig`, `.nvmrc`,
      `.gitignore`, root `README.md`, `CONTRIBUTING.md`.
- [x] 1.2 Author `Makefile` with the sprint-00 targets and tab-indented
      recipes; set `help` as the default goal.
- [x] 1.3 Author `.env.local.example` with the documented runtime variables.
- [x] 1.4 Configure `.pre-commit-config.yaml` with the ruff/mypy/import-linter
      hooks and add `make hooks` to install them.

## 2. Python project scaffolding

- [x] 2.1 Create `apps/api/pyproject.toml` (uv build, hatchling, Python 3.13)
      pinning FastAPI, uvicorn, pydantic-settings, structlog, SQLAlchemy 2
      (asyncio), asyncpg, psycopg, Alembic; dev: ruff, mypy, pytest,
      pytest-asyncio, httpx, respx, import-linter, pre-commit,
      testcontainers[postgres].
- [x] 2.2 Configure ruff (line-length 100, target-version py313, lint select
      `E,F,W,I,B,UP,RUF,N`, per-file ignore `B008` in
      `bootstrap/api.py`).
- [x] 2.3 Configure mypy in strict mode, with `mypy_path = "src"`,
      `files = ["src/shared_kernel", "src/contexts", "src/bootstrap"]`, the
      pydantic plugin, and the `testcontainers.*` override.
- [x] 2.4 Configure pytest (`asyncio_mode = "auto"`, `pythonpath = ["src"]`,
      `testpaths = ["tests"]`, `python_files = ["test_*.py"]`, markers
      `unit`, `integration`, `contract`, `e2e`). All tests live under
      `apps/api/tests/{unit,integration,contract,e2e}/`, mirroring the
      `src/` package layout; auto-markers are derived from the top-level
      folder under `tests/`.
- [x] 2.5 Add `apps/api/.importlinter` with the `domain-purity` contract.
- [x] 2.6 Add `apps/api/.python-version`.

## 3. shared_kernel.domain

- [x] 3.1 Implement `ValueObject` marker.
- [x] 3.2 Implement `Entity[IdT]` with id-based equality and hashing.
- [x] 3.3 Implement `AggregateRoot[IdT]` with `_record` / `pull_events`.
- [x] 3.4 Implement `DomainEvent` frozen, kw-only, with default `event_id` and
      `occurred_at`.
- [x] 3.5 Implement `Money` with `Decimal` coercion, currency validation,
      `__add__`/`__sub__`/`__neg__`, and `CurrencyMismatchError`.
- [x] 3.6 Unit tests for `Money` covering equality, add/sub, mixed-currency
      rejection, negative subtraction, currency-shape validation, str→Decimal
      coercion.

## 4. shared_kernel.application

- [x] 4.1 Define `UnitOfWork` Protocol (runtime-checkable) with `begin`,
      `commit`, `rollback`.
- [x] 4.2 Define `Command` and `Query` slot-only marker classes.
- [x] 4.3 Define `EventBus` Protocol + `InProcessEventBus` synchronous
      implementation with a `defaultdict[type, list[Handler]]` registry.
- [x] 4.4 Define `OutboxWriter` Protocol with the keyword-only `append`
      signature documented in the spec.

## 5. shared_kernel.adapters

- [x] 5.1 Implement `SqlAlchemyUnitOfWork`: holds a session factory, exposes
      `current_session`, `begin()` opens an `AsyncSession` with
      `session.begin()` and rolls back on exception.
- [x] 5.2 Implement `OutboxWriterSqlAlchemy.append()` using a parameterised
      `INSERT INTO outbox (...)` cast to `jsonb`, sourcing the session from
      `uow.current_session`.
- [x] 5.3 Implement `TenantContext` and `CurrentUserContext` over module-level
      `ContextVar`s with `get`/`set`/`clear`; expose a `CurrentUser`
      dataclass (`user_id: UUID`, `email: str`).
- [x] 5.4 Integration test `SqlAlchemyUnitOfWork` against a Postgres
      testcontainer: commit-on-clean-exit, rollback-on-exception,
      `current_session` raises outside `begin`.

## 6. Bootstrap (settings, db, app)

- [x] 6.1 `bootstrap/settings.py`: pydantic-settings with `.env.local` +
      `.env` sources, `git_sha` from env (no subprocess at import time),
      `database_url`, `alembic_database_url`, `cors_allowed_origins`;
      `get_settings()` cached with `lru_cache(maxsize=1)`.
- [x] 6.2 `bootstrap/db.py`: cached `AsyncEngine` (`pool_size=5`,
      `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=300`), cached
      `async_sessionmaker(expire_on_commit=False)`, `get_uow()` dependency
      yielding `SqlAlchemyUnitOfWork`.
- [x] 6.3 `bootstrap/api.py`: `create_app()` factory mounting CORS from
      settings and `/healthz` endpoint that calls `SELECT 1` and reads
      `alembic_version`; module-level `app = create_app()`.

## 7. Alembic 0001 — shared_kernel tables

- [x] 7.1 Author `apps/api/alembic.ini` (script_location, prepend_sys_path,
      logger config).
- [x] 7.2 Author `alembic/env.py`: hand-written-only (`target_metadata =
      None`), reads `ALEMBIC_DATABASE_URL` or derives psycopg URL from
      `DATABASE_URL`, runs sync via `engine_from_config`, supports offline
      mode.
- [x] 7.3 Add `alembic/script.py.mako`.
- [x] 7.4 Write migration `0001_shared_kernel`:
      enable `pgcrypto` + `citext`; create `tenants`, `users`, `outbox`
      (including `tenant_id NOT NULL`), `processed_events`,
      `idempotency_keys`, `system_info` (singleton with `CHECK (id = 1)`
      and one inserted row); create partial index
      `idx_outbox_unpublished`; implement reversible `downgrade()`.

## 8. End-to-end / integration tests

- [x] 8.1 Author root `conftest.py`: pytest auto-marker by path; session-scoped
      `postgres_container`, `database_url`, autouse `_run_migrations`
      fixture that runs `alembic upgrade head`; `session_factory` fixture.
- [x] 8.2 E2E test for `/healthz`: override `get_uow`, hit the ASGI app via
      `httpx.AsyncClient`, assert `db == "ok"` and `alembic_revision ==
      "0001_shared_kernel"`.

## 9. Local infrastructure

- [x] 9.1 Author `docker/docker-compose.yml`: compose project `nica-erp`,
      services `postgres` (17-alpine with `pg_isready` healthcheck and
      `pg_data` volume), `localstack` (3.7, `s3,sqs,events,ssm`), `mailpit`
      (1025/8025); credentials `nica_erp/nica_erp/nica_erp`.
- [x] 9.2 Author `docker/localstack-init.sh`: idempotent creation of S3 bucket
      `nica-erp-files`, SQS queues `notif-queue` + `audit-queue` and their
      DLQs, EventBridge bus `nica-erp`.

## 10. CI

- [x] 10.1 Author `.github/workflows/api-checks.yml`: triggers on push to
      `main` and PRs touching `apps/api/**`; steps `uv sync --frozen`,
      `ruff check`, `ruff format --check`, `mypy`, `lint-imports`,
      `pytest -m unit`; no deploy steps.

## 11. Verification

- [x] 11.1 Run `make doctor` on a clean host and confirm uv / pnpm / docker
      are detected.
- [x] 11.2 Run `make local-up && make migrate && make api` and confirm
      `curl http://localhost:8000/healthz` returns `db: "ok"` and the
      expected revision.
- [x] 11.3 Run `make lint` and `make test` from the repo root.
- [x] 11.4 Run `uv run lint-imports` and confirm the `domain-purity`
      contract reports `KEPT`.
