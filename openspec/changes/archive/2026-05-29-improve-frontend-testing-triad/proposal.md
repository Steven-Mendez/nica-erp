## Why

The frontend has tests, but the suite does not yet behave like a
**safety net that catches real regressions when something changes**:

- Coverage gates are locked at the baseline measured in
  `test-backfill-and-e2e-tooling`
  (`lines: 5, functions: 25, statements: 5, branches: 50` in
  `apps/web/vite.config.ts`). A PR can add an entirely uncovered
  feature and CI stays green.
- There is no `apps/web/tests/integration/` lane. The vitest suite
  conflates "unit" (a pure Zod schema) with "integration" (a route
  rendered with React Query + the router + form interaction). When a
  wiring bug breaks `/tenants/new`, no current test fails — only
  Playwright would catch it, and Playwright only covers two specs
  today (`auth.spec.ts`, `health.spec.ts`).
- Hooks are tested by mocking `openapi-fetch` ad-hoc, per file.
  Nothing enforces that the mocked shape matches the actual OpenAPI
  contract committed at `apps/web/src/api/schema.d.ts`. If the API
  renames a field, every hook test keeps passing while the live SPA
  breaks.
- Four of the five sprint-03 Playwright happy paths
  (`tenant-onboarding`, `member-management`, `permission-gating`,
  `rls-isolation`) are still unchecked in
  `openspec/changes/test-backfill-and-e2e-tooling/tasks.md` §9. The
  one e2e that exists is a layout-level smoke.
- Accessibility, contract drift, and "the form actually submits" are
  not gated anywhere — they are caught manually or by users.

The goal of this change is the testing **triad** done properly for
`apps/web/`, plus the **change-detection** mechanisms that make the
triad actually surface regressions:

1. **Unit** — pure logic (schemas, helpers, isolated hook reducers).
   Fast, no I/O, no router, no QueryClient state machine.
2. **Integration** — a route or feature slice rendered with the real
   router, real React Query, and an MSW server whose handlers are
   **typed against the generated OpenAPI schema**. This is where
   wiring bugs surface.
3. **End-to-end** — Playwright against a real backend (Postgres + API
   + SPA), covering the canonical user journeys.

On top of the triad, four quality gates make every PR prove it did
not regress something:

- **Coverage delta gate** — a PR may not lower aggregate coverage on
  `features/` and `components/`.
- **Per-slice path gate** — touching `features/X/` requires the
  integration suite for slice `X` to be green; the CI workflow
  enforces it via `paths:` filters.
- **Type-safe MSW contract** — handlers built with `openapi-msw`
  derive request/response shapes from `src/api/schema.d.ts`; a stale
  handler is a TypeScript error, not a silent test pass.
- **Accessibility gate** — every integration spec runs an `axe-core`
  assertion on the rendered route; new violations fail the build.

This is a **test-only** change. Production code under
`apps/web/src/` may only gain `data-testid` attributes; no behaviour
or styling changes.

References:

- [docs/14-testing.md](../../../docs/14-testing.md) — the triad
  baseline (backend-centric today; this change extends the frontend
  section).
- [docs/09-frontend.md](../../../docs/09-frontend.md) — feature-slice
  layout and the four rules per
  [[project_frontend_not_hexagonal]] / [[project_frontend_slice_layout]].
- [ADR-0025](../../../docs/adr/0025-testing-strategy.md) — testing
  strategy commitments.

## What Changes

### Triad layout

- Create `apps/web/tests/integration/` mirroring `src/`. The vitest
  `include` glob splits into `tests/unit/**` and
  `tests/integration/**`; the existing route render tests under
  `tests/unit/routes/` move to `tests/integration/routes/` because
  they exercise the router + React Query (a unit test does not).
- Update `apps/web/vite.config.ts` `test` block to declare three
  configurations selectable via `--project` or `--mode`: `unit`,
  `integration`, `e2e-helpers`. Coverage is collected only on the
  union, not per-project.
- Document the layout in `docs/14-testing.md` "Frontend tests"
  section (replacing the "No e2e in MVP" paragraph that the prior
  change already obsoleted).

### Integration lane (new)

- Add MSW (`msw`) and `openapi-msw` as devDependencies. Create
  `apps/web/tests/integration/msw/server.ts` (Node) and
  `apps/web/tests/integration/msw/handlers.ts`. Handlers are typed
  via `createOpenApiHttp<paths>()` from the committed
  `src/api/schema.d.ts`.
- Add `apps/web/tests/integration/_support/renderRoute.tsx` that
  wraps a route under test in the real `<RouterProvider>` +
  `<QueryClientProvider>` (fresh `QueryClient` per test) and exposes
  it as `renderRoute(path, { initialAuth?, handlers? })`.
- Author integration specs for the slices that ship user-visible
  forms or RBAC gates today:
  - `auth/{login,signup,confirm,forgot-password,reset-password}`
  - `tenants/{new, picker, members, invitations/accept}`
  - `account` profile update
  - `empresa/{settings, users}`
  - dashboard route guard
- Each integration spec asserts:
  - The expected request was sent to MSW (URL, method, body).
  - The success and the documented error responses
    (`401`, `403`, `404`, `409`, `422`) render the right UI.
  - An `axe-core` run on the final rendered DOM reports no
    violations of `wcag2a`+`wcag2aa`.

### Unit lane (tightened)

- Move route render tests out (see above) so `tests/unit/` only
  contains true units: Zod schemas, `lib/`, `api/queryKeys.ts`,
  `api/tokenStore.ts`, isolated hook reducers, the
  `app-sidebar/sidebar-context` reducer, etc.
- Remove ad-hoc `openapi-fetch` mocks from existing hook tests; the
  hook tests that need a network round-trip move down into
  integration. Pure schema and helper tests stay in unit.

### E2E lane (real backend)

- Replace today's `webServer: pnpm dev` block with a script that, in
  CI, boots Postgres + API + SPA (the same recipe `make test-all`
  uses locally) so Playwright exercises the actual `/v1/*` contract,
  not just the dev server with no API. Locally,
  `reuseExistingServer: true` continues to allow running against an
  already-up stack for the fast loop.
- Backfill the four missing sprint-03 specs from
  `test-backfill-and-e2e-tooling` §9 (`tenant-onboarding`,
  `member-management`, `permission-gating`, `rls-isolation`) plus
  the new `dashboard-empty-state` spec for the empresa onboarding
  path.
- Tag each spec with `@smoke` (must pass on every PR) or
  `@critical` (allowed to run nightly on WebKit). Playwright
  `project.grep` selects per CI job, per
  [Playwright `grep` docs](https://playwright.dev/docs/api/class-testproject#test-project-grep).
- Shard the Playwright run on CI when total runtime crosses ~3 min
  using `--shard=N/M` per the
  [official sharding pattern](https://playwright.dev/docs/test-sharding).

### Quality gates (change-detection)

- **Coverage delta**: a CI step diffs the
  `coverage/coverage-summary.json` between `main` and the PR head;
  the job fails when aggregate `lines` or `branches` drop. Implement
  via the `coverage-diff` step in `web-checks.yml`; no third-party
  service.
- **Per-file thresholds for `features/` and `components/`** using
  vitest's documented
  [`coverage.thresholds` glob form](https://vitest.dev/config/#coverage-thresholds)
  so a single uncovered file is visible by name in the failure
  output, not lost in the aggregate.
- **Threshold ratchet**: thresholds use `autoUpdate` set to
  `Math.floor` in a dedicated `pnpm test:run --coverage --update`
  invocation. CI never runs `autoUpdate`; only the local maintainer
  recipe does, after a verified coverage increase.
- **Type-safe MSW**: `openapi-msw` makes a stale handler a
  TypeScript error. `pnpm typecheck` already runs in CI; the
  contract check rides on it.
- **Accessibility**: `vitest-axe` matcher in every integration
  spec; baseline allow-list is empty.
- **CI fan-out**: the `web-checks.yml` workflow runs four jobs
  (`unit`, `integration`, `e2e-smoke`, `coverage-delta`). A
  `paths:` filter on `apps/web/src/features/<x>/**` adds the slice's
  integration shard to the matrix.

### Tooling

- New Makefile recipes:
  - `make test-fe-unit`
  - `make test-fe-integration`
  - `make test-fe-e2e`
  - `make test-fe-all` (the three lanes plus coverage and
    `pnpm typecheck`).
- Update `make test-all` to call the new fe lanes alongside the
  backend lanes.

### Out of scope

- No backend test changes (backend triad is owned by
  `test-backfill-and-e2e-tooling` and `docs/14-testing.md`).
- No mutation testing, no fuzzing, no visual regression / screenshot
  diffing in this sprint — Playwright traces remain the failure
  artefact.
- No third-party coverage host (Codecov, Coveralls). The delta gate
  runs in-workflow.
- No changes to feature behaviour, no new ADRs, no new migrations.

## Impact

- **Affected specs**: `frontend-testing-triad` (new),
  `frontend-testing-change-detection` (new).
- **Affected code**:
  - `apps/web/tests/{unit,integration}/` — reorganised; new
    integration tree.
  - `apps/web/tests/integration/msw/`,
    `apps/web/tests/integration/_support/` — new.
  - `apps/web/vite.config.ts` — projects, coverage globs, ratchet.
  - `apps/web/playwright.config.ts` — real-backend `webServer` in
    CI, tag-based grep, sharding hooks.
  - `apps/web/package.json` — `msw`, `openapi-msw`, `vitest-axe`,
    `axe-core` devDependencies; new scripts.
  - `apps/web/src/**` — `data-testid` annotations only.
  - `.github/workflows/web-checks.yml` — fan-out into `unit`,
    `integration`, `e2e-smoke`, `coverage-delta` jobs.
  - `Makefile` — new recipes.
- **Affected docs**:
  [`docs/14-testing.md`](../../../docs/14-testing.md) — replace the
  "Frontend tests" subsection with the triad description and the
  change-detection gate list.
- **Sprint envelope**: this is sprint-follow-up tooling, not a
  feature. It lands before any sprint that ships forms or RBAC
  surfaces so those sprints inherit the safety net.

## Coverage commitment — every current SPA capability is verified

The change is not "raise coverage to N%". It is "every user-visible
functionality that exists today has at least one test at the layer
that owns it, and changes to any of them surface a failing test
before merge." `tasks.md` enumerates the full matrix; the
high-level inventory below is the contract.

### Routes (22)

- Identity / public:
  `__root`, `/login`, `/signup`, `/confirm`, `/forgot-password`,
  `/reset-password`, `/welcome`.
- Authenticated shell:
  `/account`, `/dashboard`, `/onboarding`, `/settings`, `/sales`,
  `/reports`, `/inventory`, `/health`.
- Tenant onboarding & lifecycle:
  `/tenants`, `/tenants/new`.
- Empresa surface (current term):
  `/empresa`, `/empresa/settings`, `/empresa/users`.
- Invitation deep-link: `/invitations/$token`.

Every route SHALL have (a) an integration test covering its render
under unauthenticated, authenticated, and the documented role
contexts, and (b) e2e coverage if it is part of a canonical user
journey (auth → tenant onboarding → member management → empresa
admin).

### Feature slices

- `features/auth/` — 11 hooks, 7 Zod schemas, `AuthLayout`. Each
  hook gets an integration test; each schema gets a unit test.
- `features/tenants/` — 12 hooks, 4 Zod schemas, 4 components
  (`DataTableFacetedFilter`, `InvitationsTable`, `InviteMemberDialog`,
  `MembersTable`), `municipalities.ts`. Same triad applies; the
  `municipalities` catalog gets a contract test that asserts each
  canonical name round-trips.
- `features/dashboard/` — 4 components, `index.ts` export surface.
  Component snapshot/behaviour tests at the unit layer; render
  through `/dashboard` integration.

### Shared infrastructure

- `api/{client, errors, interceptor, queryKeys, tokenStore,
  useHasPermission, healthz}` — every module covered by unit
  tests; the interceptor refresh-cycle covered by integration with
  MSW driving the 401-then-200 round-trip.
- `lib/{route-guard, useDocumentTitle, utils}` — unit tests for
  every exported helper.
- `components/app-shell/{app-shell, site-header}`,
  `components/app-sidebar/{app-sidebar, sidebar-context, sidebar,
  tenant-switcher}`,
  `components/{account-menu, brand-header, theme-provider,
  theme-toggle, identity-layout, logo}` — behaviour-level tests
  (collapse, persisted state, active nav, tenant switch, sign-out)
  at the layer that exercises the behaviour (unit for reducers,
  integration for the rendered shell).
- `components/ui/*` — `button`, `input`, `field`, `dialog`,
  `dropdown-menu`, `select`, `popover`, `command`, `calendar`,
  `date-picker`, `input-otp`, `tabs`, `toggle`, `toggle-group`,
  `checkbox`, `tooltip`, `alert`, `badge`, `table`, `separator`,
  `progress`, `skeleton`, `textarea`, `card`, `label`,
  `input-group`. Each wrapper that diverges from upstream shadcn
  gets a unit test for the divergence; the rest are covered
  transitively by the integration suite (no per-file gate).

### Verification matrix output

`make test-fe-all` SHALL emit a `verification-matrix.json` mapping
every entry above to the test(s) that cover it. The file is
checked into `apps/web/coverage/` and the CI artefact upload makes
it inspectable on every PR — the user-facing question "is feature
X tested?" has a one-line answer.
