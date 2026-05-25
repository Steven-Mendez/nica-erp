# ADR-0025 — Testing strategy

**Status**: Accepted
**Date**: 2026-05-23

## Context
Pre-implementation, every sprint claims test coverage as part of DoD ([`../sprints/README.md`](../sprints/README.md)), but no document defines what each test level targets, what to mock, or what gates merge. The risk: in a hexagonal + multi-tenant + fiscal-compliance system, ad-hoc testing leaves the highest-value invariants (RLS isolation, fiscal numbering atomicity, port-contract parity across local/AWS adapters) under-covered while unit tests proliferate around the domain.

## Decision
**Four test levels, each owns a specific failure class.** Tests live under `apps/<api|web>/tests/{unit,integration,contract,e2e}/`, mirroring the layout of `src/` — the top-level folder under `tests/` selects the marker auto-applied by `conftest.py` (`pytest -m unit` / `-m integration` filter without per-file boilerplate).

| Level | Where | What it owns | Speed budget |
|---|---|---|---|
| Unit | `tests/unit/<mirrors src/>` (covers `<context>/domain/`, `<context>/application/`, `shared_kernel/domain/`, `shared_kernel/application/`) | Pure logic: invariants, value objects, use case orchestration. No I/O. | < 1 ms per test |
| Integration | `tests/integration/<mirrors src/>` (covers `<context>/adapters/`, `shared_kernel/adapters/`, and infra) | One adapter at a time against real dependencies (testcontainers Postgres, LocalStack S3/EventBridge, Mailpit). | < 1 s per test |
| Contract | `tests/contract/` | One test per port, parametrized over **all adapters** (e.g., `IdentityProviderLocal` + `IdentityProviderCognito`). Proves swap is safe. | < 5 s per test |
| End-to-end | `tests/e2e/` | One canonical flow per sprint through HTTP → DB → outbox → consumer. Run against the real local stack. | < 30 s per test |

### Always-on gates
- **RLS isolation test** — for every tenant-scoped table, an integration test confirms tenant A cannot SELECT, UPDATE, or DELETE tenant B's rows, even with an unset GUC. Pattern in [`../14-testing.md`](../14-testing.md).
- **N+1 query gate** — list/aggregate use cases assert `assert_query_count(N)` via SQLAlchemy event hooks. Sprint 06 (monthly IR accumulation) is the first that requires it; the pattern is reused thereafter.
- **Concurrent number sequence test** — fiscal numbering ([ADR-0008](0008-for-update-sequence-allocation.md)) has an integration test that issues N invoices concurrently and asserts no gaps or duplicates.
- **Contract test parity** — every port with both a local and AWS adapter ships a parametrized contract test by the end of sprint 09 ([`../sprints/09-mvp-validation.md`](../sprints/09-mvp-validation.md)).

### Coverage targets
- `domain/` + `application/`: ≥ 70% line coverage. Enforced in CI ([ADR-0023](0023-no-ci-cd-mvp.md)).
- `adapters/`: no line-coverage target — adapters are exercised by integration tests; the bar is "every method called by application is tested".
- Total coverage is not a target — it incentivizes the wrong tests.

### What we do not test
- ORM mapping correctness in isolation (integration tests cover it).
- Framework internals (FastAPI request lifecycle, SQLAlchemy session behavior).
- Generated code (OpenAPI clients, Alembic migrations) — exercised end-to-end.

## Consequences
- (+) Each test failure points to a specific layer.
- (+) Contract tests give confidence to swap adapters during rolling deploys ([ADR-0018](0018-rolling-deploys.md)).
- (+) RLS and concurrency tests catch the failures that hurt most in multi-tenant fiscal systems.
- (+) `tests/` mirror tree keeps source clean (no `*_test.py` neighbors) and makes the marker auto-tagger a single `conftest.py` rule keyed on the top-level folder.
- (−) Integration tests need testcontainers + LocalStack — slower to bootstrap than pure-mock alternatives.
- (−) Contract tests add a per-port one-time authoring cost — paid once, valued forever.
- (−) Coverage gate creates pressure to test trivial paths — accepted: 70% is low enough that this risk is bounded.

## Alternatives
- **Heavy mocking, no integration tests** — rejected: hides multi-tenancy, RLS, and migration bugs until production.
- **Single E2E layer covering everything** — rejected: slow feedback, hard to localize failures.
- **Coverage target ≥ 90%** — rejected: encourages tests for the sake of the gate, not for the sake of confidence.
- **BDD (Cucumber/behave)** — rejected: parallel vocabulary on top of pytest with no team benefit for a single dev.

## Revisit triggers
- A production incident traces back to a missing test class (e.g., RLS bypass via a code path the canonical test didn't exercise) → add the class.
- Contract test runtime exceeds 5 minutes total → split per port or move to a nightly job.
- Second contributor lands → re-evaluate whether the coverage target should rise.
- Integration test flakiness > 2% → invest in test data isolation (per-test database, schema reset) rather than retry.
