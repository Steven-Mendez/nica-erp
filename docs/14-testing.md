# 14 — Testing

How tests are organized, what each level owns, and the patterns that catch the highest-value bugs in a multi-tenant fiscal system. Strategy commitments live in [ADR-0025](adr/0025-testing-strategy.md); this document is the how.

---

## Levels

Four levels, each owns a specific failure class. Tests live under `apps/<api|web>/tests/{unit,integration,contract,e2e}/` mirroring `src/`; `apps/api/conftest.py` auto-applies the marker matching the top-level folder.

| Level | Where | What it owns | Speed budget |
|---|---|---|---|
| **Unit** | `tests/unit/<mirrors src/>` (e.g. `tests/unit/contexts/sales/domain/`, `tests/unit/shared_kernel/domain/`) | Pure logic, invariants, value objects, use case orchestration. No I/O. | < 1 ms per test |
| **Integration** | `tests/integration/<mirrors src/>` (e.g. `tests/integration/contexts/sales/adapters/`, `tests/integration/shared_kernel/adapters/`) | One adapter at a time against real dependencies (testcontainers Postgres, LocalStack S3/EventBridge, Mailpit) | < 1 s per test |
| **Contract** | `tests/contract/` | One test per port, parametrized over **all adapters** (e.g., `IdentityProviderLocal` + `IdentityProviderCognito`). Proves swap is safe. | < 5 s per test |
| **End-to-end** | `tests/e2e/` | One canonical flow per sprint through HTTP → DB → outbox → consumer | < 30 s per test |

Markers: `pytest -m unit`, `-m integration`, `-m contract`, `-m e2e`.

---

## Layout

Tests live under `apps/<api|web>/tests/{unit,integration,contract,e2e}/`, mirroring the source layout — **not** co-located next to source modules.

```
apps/api/
├── src/
│   └── contexts/
│       └── sales/
│           ├── domain/
│           │   └── invoice.py
│           ├── application/
│           │   └── issue_invoice.py
│           └── adapters/
│               ├── persistence/
│               │   └── invoice_repository.py
│               └── http/
│                   └── invoice_router.py
└── tests/
    ├── unit/
    │   └── contexts/sales/
    │       ├── domain/test_invoice.py
    │       └── application/test_issue_invoice.py
    ├── integration/
    │   └── contexts/sales/adapters/
    │       ├── persistence/test_invoice_repository.py
    │       └── http/test_invoice_router.py
    ├── contract/
    │   └── test_identity_provider_contract.py
    └── e2e/
        └── test_invoice_issuance_e2e.py
```

`apps/api/conftest.py` auto-marks tests by the top-level folder under `tests/`: `tests/unit/` → `unit`, `tests/integration/` → `integration`, `tests/contract/` → `contract`, `tests/e2e/` → `e2e`. No per-file marker boilerplate. `pytest -m unit` filters correctly out of the box.

---

## Fixtures

### Database

Integration and e2e use a real Postgres via `testcontainers`. Each test runs inside a transaction that rolls back at teardown — no schema reset between tests.

```python
@pytest.fixture
async def session(db_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        trans = await conn.begin()
        async_session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield async_session
        finally:
            await async_session.close()
            await trans.rollback()
```

Migrations run once at testcontainer startup (`alembic upgrade head`).

### Tenant context

```python
@pytest.fixture
async def tenant_a(session: AsyncSession) -> Tenant:
    tenant = await create_tenant(session, name="Tenant A", timezone="America/Managua")
    return tenant

@pytest.fixture
async def with_tenant_a(session: AsyncSession, tenant_a: Tenant):
    await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_a.id)})
    yield tenant_a
```

### Actor (RBAC)

```python
@pytest.fixture
async def admin_actor(session: AsyncSession, tenant_a: Tenant) -> Actor:
    user = await create_user(session)
    await assign_role(session, tenant_a.id, user.id, "admin")
    return await load_actor(session, user.id, tenant_a.id)
```

### Clock

`ClockMock` exposed via the `Clock` port — every use case takes a clock; tests provide a fixed instant.

---

## Patterns that pay rent

### RLS isolation test

Every tenant-scoped table ships a test that confirms tenant B cannot SELECT, UPDATE, or DELETE tenant A's rows. The test runs even when `app.tenant_id` is unset.

```python
@pytest.mark.integration
async def test_invoice_rls_isolation(session_t_a, session_t_b, tenant_a, tenant_b):
    await session_t_a.execute(
        insert(InvoiceRow).values(tenant_id=tenant_a.id, ...)
    )
    await session_t_a.commit()

    # Tenant B context cannot see tenant A's invoice.
    result = await session_t_b.execute(select(InvoiceRow))
    assert result.scalars().all() == []

    # Unset GUC sees nothing.
    await session_t_b.execute(text("RESET app.tenant_id"))
    result = await session_t_b.execute(select(InvoiceRow))
    assert result.scalars().all() == []
```

Lives next to the migration that adds RLS for the table. If a table is added without one, the sprint doesn't pass DoD.

### N+1 gate

For any list/aggregate use case, assert a query budget. SQLAlchemy event hooks count queries; the test fails if the count exceeds the budget.

```python
from shared_kernel.testing import assert_query_count

@pytest.mark.integration
async def test_list_invoices_does_not_explode(session, with_tenant_a, ten_invoices):
    async with assert_query_count(session, max_queries=3):
        invoices = await invoice_repo.list(actor=admin_actor)
        # access related fields that could trigger lazy loads
        for inv in invoices:
            inv.customer.legal_name
            inv.lines
```

`assert_query_count` is a context manager in `shared_kernel/testing/`. Budget is per use case; lazy loads inflate the count.

**Sprint 06** (monthly IR accumulation) is the first to require this. Subsequent list-heavy use cases inherit the pattern. The gate is referenced from the sprint's exit criteria.

### Concurrent number-sequence test

Fiscal numbering ([ADR-0008](adr/0008-for-update-sequence-allocation.md)) must produce no gaps and no duplicates under concurrent issuance.

```python
@pytest.mark.integration
async def test_concurrent_invoice_issuance(with_tenant_a, ten_users):
    async def issue_one(user):
        async with new_session() as s:
            await s.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_a.id})
            return await issue_invoice(s, actor=user, ...)

    invoices = await asyncio.gather(*(issue_one(u) for u in ten_users))
    numbers = sorted(int(i.number.split("-")[-1]) for i in invoices)
    assert numbers == list(range(1, 11))   # no gaps, no duplicates
```

### Permission matrix test

Per [06 — Security model](06-security-model.md), the role-to-permission matrix is canonical. Sprint 03 enumerates it as a parametrized test that loads the seed and compares to the constant in `shared_kernel/permissions/catalog.py`.

```python
@pytest.mark.integration
@pytest.mark.parametrize("role,permission,expected", DEFAULT_MATRIX)
async def test_role_has_permission(session, role, permission, expected):
    assert await role_has(session, role, permission) is expected
```

### Contract test (port × adapters)

```python
@pytest.mark.contract
@pytest.mark.parametrize(
    "provider_factory",
    [
        pytest.param(make_local_provider, id="local"),
        pytest.param(make_cognito_provider, id="cognito"),
    ],
)
async def test_register_then_authenticate(provider_factory):
    provider = provider_factory()
    email = f"contract-{uuid4()}@{settings.alert_email.split('@')[1]}"
    await provider.register(SignupData(email=email, password="ContractTest1!@"))
    await provider.confirm_signup(email=email, code=get_test_code(email))
    identity = await provider.authenticate(Credentials(email=email, password="ContractTest1!@"))
    assert identity.email == email
    assert identity.access_token is not None
```

Run only against a deployed environment (`pytest -m contract`). Not part of `make test`. Sprint 09 consolidates these.

---

## Coverage targets

- `domain/` + `application/`: ≥ 70% line coverage. Enforced in CI.
- `adapters/`: no line target — exercised by integration tests; bar is "every method called by application is tested".
- Total coverage is **not** a target — incentivizes the wrong tests.

---

## What we don't test

- ORM mapping correctness in isolation (integration tests cover it).
- Framework internals (FastAPI request lifecycle, SQLAlchemy session behavior).
- Generated code (OpenAPI clients, Alembic migration files) — exercised end-to-end.

---

## Frontend tests

`apps/web/`:
- **Component tests** with Vitest + Testing Library. Critical flows only — login, list views, the forms that drive fiscal-relevant operations.
- **No e2e in MVP**. Playwright is the candidate when introduced; see [18 — Roadmap](18-roadmap.md).
- **Typecheck is the first gate** — `pnpm typecheck` exit 0. Most regressions catchable in CI.

---

## CI

Per [ADR-0023](adr/0023-no-ci-cd-mvp.md):

| Workflow | Triggers | Runs |
|---|---|---|
| `api-checks.yml` | push, PR | `ruff`, `mypy --strict` on `domain`/`application`, `import-linter`, `pytest -m unit` |
| `web-checks.yml` | push, PR | `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, `pnpm test --run` |

Integration tests run locally and pre-deploy (manual). Contract tests run against a deployed environment (manual, sprint 09 consolidates).

---

## Adding tests for a new feature

Checklist:
1. **Unit** for any new aggregate method or use case.
2. **Integration** for any new adapter (the only test that talks to its real dependency).
3. **RLS isolation** for any new tenant-scoped table.
4. **N+1 gate** for any new list endpoint or aggregate-fan-out query.
5. **Contract** for any new port with both adapters (one parametrized test, both adapters under it).
6. **E2E** for the sprint's canonical flow.

If any item is missing without a documented reason, the sprint does not close.

---

## References
- [ADR-0025](adr/0025-testing-strategy.md) — strategy commitments
- [ADR-0023](adr/0023-no-ci-cd-mvp.md) — CI scope
- [ADR-0002](adr/0002-postgres-rls.md) — RLS that the isolation test enforces
- [ADR-0008](adr/0008-for-update-sequence-allocation.md) — number sequence concurrency contract
- [06 — Security model](06-security-model.md) — permission matrix canonical source
- [16 — Tooling](16-tooling.md) — pytest, ruff, mypy configuration
