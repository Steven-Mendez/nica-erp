## Context

This change stacks on top of
[`add-multi-tenancy-and-rbac`](../add-multi-tenancy-and-rbac/proposal.md)
and [`add-frontend-dashboard-shell`](../add-frontend-dashboard-shell/proposal.md).
The architectural envelope is fixed by:

- [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md)
  — including the follow-up section that this change implements.
- [`docs/04-testing-strategy.md`](../../../docs/04-testing-strategy.md)
  — the triad (unit/integration/e2e) baseline.
- [`feedback_test_layout`](file:///Users/wern/.claude/projects/-Users-wern-Documents-GitHub-nica-erp/memory/feedback_test_layout.md)
  — backend and frontend tests live under
  `apps/<api|web>/tests/{unit,integration,e2e}/` mirroring `src/`,
  never co-located with source.

The change is **test-only**: there is no production code shape to
re-design, no migration to author, no API contract to evolve. The
design surface is the *tooling* (Playwright, pytest-cov, vitest
coverage) and the *gate thresholds*.

## Goals / Non-Goals

**Goals**

- A single `make test-all` runs the full triad locally and in CI;
  the run is reproducible from a clean clone.
- Coverage gates fail merges below the thresholds. The thresholds
  are documented and tied to specific source trees, not the whole
  repo.
- The missing sprint-03 RLS isolation gate lands and is enforced.
- The Playwright suite covers the five happy paths called out in
  the sprint follow-up and runs on Chromium in CI; WebKit is
  configured but warning-only until a flake budget is established.

**Non-Goals**

- No mutation testing, no fuzzing, no property-based testing
  (deferred until there is a recurring class of bugs that needs
  them).
- No visual regression / screenshot diffing in this sprint —
  Playwright captures traces and screenshots only as failure
  artifacts.
- No load testing or performance gates.
- No CI parallelisation beyond default vitest/pytest workers.

## Decisions

### 1. Playwright over Cypress / vitest-only

Decision: install `@playwright/test` (Chromium + WebKit projects)
as the frontend e2e tool. Vitest + Testing Library remain the unit
and integration layer.

Rationale: Playwright auto-waits, native multi-browser support, and
a maintained CLI for CI install (`playwright install --with-deps`).
Cypress is mature but its single-browser-per-suite model is
awkward for the cross-tenant scenarios we need.

### 2. Coverage thresholds are tree-scoped

Decision: backend ≥ 90% lines on
`apps/api/src/contexts/tenants`, `apps/api/src/contexts/identity`,
and `apps/api/src/shared_kernel`. Frontend ≥ 80% lines on
`apps/web/src/features` and `apps/web/src/components`. The
thresholds are configured per `--cov` invocation, not globally,
so future code in `apps/api/src/bootstrap` does not raise the bar
prematurely.

Rationale: gates that apply to the whole tree push contributors
to write tests for trivial modules (bootstrap glue, generated
clients) just to satisfy a single number. Tree-scoped thresholds
target the code where bugs hurt.

### 3. Playwright fixtures encapsulate auth and tenant setup

Decision: `apps/web/tests/e2e/fixtures/auth.ts` exposes
`loginAs(page, { email })` that drives the SPA's login UI once
per test, plus `signupConfirmAndLogin(page, { email })` for the
full bootstrap. `tenant.ts` exposes
`createTenant(page, fixtureData)` that runs the existing
`/tenants/new` form end-to-end. No HTTP shortcuts: the fixtures
go through the same UI a real user would, so the fixture itself
is a smoke test.

Rationale: API shortcuts in e2e fixtures hide regressions in the
very flows under test. The cost is a few extra seconds per spec,
paid back the first time the signup form breaks and the fixture
fails loudly.

### 4. RLS isolation gate is implemented in both layers

Decision: the sprint-03 gate
`tests/e2e/contexts/tenants/test_rls_tenant_isolation.py` is
implemented in pytest (driving the API directly with
`forge_jwt`). A Playwright spec
`apps/web/tests/e2e/rls-isolation.spec.ts` mirrors the scenario
from the SPA. Both are merge gates.

Rationale: the pytest version protects the API contract; the
Playwright version protects the SPA's routing and the tenant
switcher's cache-invalidation behaviour. They guard distinct
regression vectors.

### 5. `data-testid` annotations are the only allowed production diffs

Decision: production code under `apps/api/src/` and
`apps/web/src/` may gain `data-testid` attributes on components
that Playwright needs to select; nothing else changes. Any other
edit to production code makes a PR ineligible for this sprint
and belongs to sprint 3.6.

Rationale: the safety net only matters if it is laid *before*
the code moves. Mixing in fixes blurs the line and defeats the
purpose.

## Risks / Trade-offs

- **CI runtime grows ~3-5 minutes** when the Playwright job runs.
  Mitigation: a single Playwright job, two workers, Chromium only
  on the merge gate; the WebKit run is nightly.
- **Cognito stub coverage gap**: e2e auth runs against
  `IdentityProviderLocal` which reads the verification code from
  the in-process mail sink. Real Cognito flows are exercised by
  the sprint-09 contract tests, not here. Documented in
  `apps/web/tests/e2e/README.md`.
- **Coverage gates can incentivise low-value tests**. Mitigation:
  the gates are tree-scoped and the PR template asks reviewers to
  flag "tests that exist only to satisfy coverage".

## Migration plan

1. Land the OpenSpec change with proposal/design/tasks. Specs
   reference the sprint doc, not the inverse.
2. Implement unit/integration tests against the existing source
   (no production changes). Each PR is reviewable on its own.
3. Implement e2e tests, adding `data-testid` attributes as
   needed. Each `data-testid` addition is justified in its PR.
4. Wire CI; the merge gate flips on once the suite is green for
   three consecutive runs.
5. Update the sprint doc's final note with the achieved coverage
   numbers.

## Open Questions

- WebKit flake budget: under what failure rate do we promote it
  from warning-only to merge gate? Deferred to the closure note
  of sprint 3.5.
- Coverage report artifacting: HTML reports as a CI artifact is
  configured here; a long-term home (e.g. Codecov) is a sprint
  3.7+ topic.
