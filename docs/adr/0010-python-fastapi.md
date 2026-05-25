# ADR-0010 — Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic

**Status**: Accepted
**Date**: 2026-05-23

## Context
Single dev pre-launch, fiscal domain (DGI PDFs, IVA/kardex XLSX, BCN scraping), hexagonal + DDD ([ADR-0001](0001-hexagonal-architecture.md)), Fargate API + Lambda workers from the same Dockerfile ([ADR-0004](0004-ecs-not-lambda.md)), concurrent I/O requiring native async.

## Decision
Python 3.12, FastAPI, SQLAlchemy 2.0 async on `asyncpg`, Alembic. Pydantic v2 for DTOs and event validation. Imperative mappers in `adapters/outbound/persistence/sqlalchemy/`, never touch the domain. Unit of Work over `AsyncSession`, commit/rollback in application. Session events inject `SET LOCAL app.tenant_id` ([ADR-0002](0002-postgres-rls.md)) and flush `outbox` ([ADR-0006](0006-transactional-outbox.md)). Migrations as one-off ECS task. Dependencies with `uv`; format/lint with `ruff`.

## Consequences
- (+) Fiscal ecosystem covered without glue code; OpenAPI feeds the frontend client ([ADR-0009](0009-frontend-stack.md)).
- (+) SQLAlchemy 2.0 async supports Unit of Work without Active Record.
- (+) Same Dockerfile for the Fargate API and Lambda workers.
- (−) Lower raw throughput than Go/Java; acceptable, the bottleneck is the DB ([ADR-0008](0008-for-update-sequence-allocation.md)).
- (−) Optional typing; mitigated with `mypy --strict` on `domain/` + `application/` via pre-commit.
- (−) SQLAlchemy 2.0 async has sharp edges (`expire_on_commit`, lazy loads outside session); documented in the shared kernel.
- (−) Imperative mapper more verbose than Active Record; cost accepted by [ADR-0001](0001-hexagonal-architecture.md).

## Alternatives
- **Node.js 20 + NestJS + Prisma** — rejected: PDF/XLSX less mature; Prisma couples domain to the schema.
- **Go 1.22 + gin/echo + sqlc** — rejected: verbose for VOs and repos; PDF depends on limited C bindings.
- **Java 21 + Spring Boot + JPA** — rejected: cognitive cost and Fargate cold starts, over-engineered for [ADR-0001](0001-hexagonal-architecture.md).
- **asyncpg + raw SQL** — rejected: discards Unit of Work, manual mapping, complex in-memory tests.
- **Tortoise ORM** — rejected: Active Record incompatible with the dependency rule.
- **yoyo / sqitch** — rejected: yoyo does not autogenerate; sqitch forces an extra DSL.
- **Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic** — chosen.

## Revisit triggers
- DB throughput becomes the bottleneck and async I/O is no longer the dominant cost.
- Fiscal libraries (PDF/XLSX) for another language reach parity and reduce maintenance burden.

Detail in [`../02-architecture.md`](../02-architecture.md).
