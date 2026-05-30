## Why

Sprint 03 closed with the `tenants` bounded context shipped, the
RBAC catalog wired, and migration 0003 applied — but the test
inventory does not match the implementation. The nine tenants use
cases have zero unit tests, the three tenant repositories have zero
integration tests, the eleven tenant routes are exercised only by
the generic permission-coverage check, and the canonical
`test_tenant_isolation_via_rls` declared as the sprint-03 merge
gate **never landed on disk**. On the frontend the situation is
worse: three vitest files total, Playwright not installed, no
browser-level e2e coverage at all.

Sprint 3.6 will rename the user-facing vocabulary
("tenant" → "organization", per
[ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md)),
ship a Welcome screen, a Supabase-style organization picker, a
four-step creation wizard, and an invitation-token transport
change ([ADR-0031](../../../docs/adr/0031-invitation-token-transport.md)).
That work touches ~150 frontend imports and the `/v1/me` API
contract. Doing it without a safety net is reckless. This change
exists to lay the net first.

Reference: [`docs/sprints/03-tenants-and-rls.md` — Sprint follow-up — Test backfill & e2e tooling](../../../docs/sprints/03-tenants-and-rls.md#sprint-follow-up--test-backfill--e2e-tooling-sprint-35-2026-05-27).

## What Changes

### Backend

- Add unit tests for the nine `contexts/tenants/application/use_cases/*`
  modules, each mocking repositories, the outbox and the identity
  provider; asserting command shape, domain invariants, and emitted
  events.
- Add integration tests for the three tenants persistence adapters
  (`TenantRepository`, `MembershipRepository`, `InvitationRepository`),
  the JWT token generator, the `TenantMiddleware`, the eleven tenant
  HTTP routes, and the invitations router.
- Add the missing sprint-03 gate test
  `tests/e2e/contexts/tenants/test_rls_tenant_isolation.py`
  (matches the scenario documented in the sprint above).
- Add a tenant-lifecycle e2e (`test_tenant_lifecycle.py`).
- Add `pytest-cov` configuration and a `make test-be-coverage` recipe
  that enforces ≥ 90% line coverage on `contexts/tenants`,
  `contexts/identity` and `shared_kernel`.

### Frontend

- Add vitest unit tests for every existing hook, component, schema,
  and shared helper in `apps/web/src/features/{auth,tenants,dashboard}`,
  `apps/web/src/components/{app-shell,app-sidebar,ui}`, and
  `apps/web/src/api/`.
- Add vitest + MSW route render tests for every route under
  `apps/web/src/routes/`.
- Install `@playwright/test`, author `playwright.config.ts` and
  fixtures, and add five Playwright specs covering authentication,
  tenant onboarding, member management, permission gating, and
  cross-tenant isolation.
- Add a vitest v8 coverage configuration enforcing ≥ 80% line
  coverage on `features/` and `components/`.

### Tooling and CI

- `make test-e2e`, `make test-be-coverage`, `make test-fe-coverage`,
  `make test-all` recipes.
- A new CI job that installs Chromium + WebKit via
  `npx playwright install --with-deps`, brings up Postgres + API +
  SPA, runs the Playwright suite, and uploads
  `playwright-report/` as an artifact on failure.
- `.gitignore` entries for `playwright-report/` and `test-results/`.

### Out of scope

- No production code changes. The only diffs under
  `apps/api/src/` and `apps/web/src/` are `data-testid` attributes
  where Playwright requires deterministic selectors.
- No new features, migrations, ADRs, or API contracts. Sprint 3.6
  ships those on top of this safety net.

## Impact

- Affected specs: `e2e-tooling` (new), `test-coverage` (new).
- Affected code:
  - `apps/api/tests/unit/contexts/tenants/`
  - `apps/api/tests/integration/contexts/tenants/`
  - `apps/api/tests/e2e/contexts/tenants/`
  - `apps/api/pyproject.toml` (coverage config)
  - `apps/web/tests/unit/`, `apps/web/tests/integration/`
  - `apps/web/tests/e2e/` (new — Playwright)
  - `apps/web/package.json`, `apps/web/playwright.config.ts`,
    `apps/web/vitest.config.ts`
  - `apps/web/src/components/**/*.tsx` and
    `apps/web/src/routes/**/*.tsx` (test-id annotations only)
  - `.github/workflows/` (new e2e job)
  - `Makefile`
- Affected docs: the sprint 3.5 follow-up section appended to
  [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md).

## Carry-over (2026-05-30)

Superseded by goal `.claude/goals/pre-sprint-04.md` tasks 8 (Playwright fixtures) and 9 (the four remaining specs). Backend + frontend unit/integration coverage from this change is complete; the e2e and 5 route-render gaps remain.
