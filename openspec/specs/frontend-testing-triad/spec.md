# frontend-testing-triad Specification

## Purpose

`apps/web/` runs the same triad as the backend, organised into three
explicit lanes under `apps/web/tests/{unit,integration,e2e}/`. Each
lane owns a specific failure class and forbids the patterns that
belong to the lane below or above it. Vitest is configured with two
named projects (`unit`, `integration`) so each lane has its own
setup, timeout, and runtime budget; Playwright provides the e2e
layer with tag-based selection (`@smoke` for every PR,
`@critical` for the nightly cron). MSW handlers are typed against
the committed OpenAPI schema via `openapi-msw`, so a renamed
response field becomes a TypeScript error at `pnpm typecheck`
instead of a silent green test against a stale shape. A
verification matrix script enumerates the SPA inventory (routes,
hooks, schemas, shared infra, components) and fails the build when
any entry has zero covering tests.

## Requirements

### Requirement: Frontend test tree mirrors the triad with three explicit lanes

The repository SHALL contain three sibling directories under
`apps/web/tests/`:

- `tests/unit/` — pure logic only: Zod schemas, helpers in
  `src/lib/`, the `sidebar-context` reducer, isolated functions in
  `src/api/{queryKeys,tokenStore,useHasPermission,errors,
  interceptor (pure pieces only)}`. No `QueryClient`, no router,
  no MSW.
- `tests/integration/` — feature flows rendered with the **real**
  TanStack Router and a fresh `QueryClient`, with HTTP intercepted
  by an MSW server typed via `openapi-msw` against
  `src/api/schema.d.ts`. The lane owns route render, form
  interaction, error UI, redirects, and accessibility assertions.
- `tests/e2e/` — Playwright specs against a real backend
  (Postgres + API + SPA) covering the canonical user journeys.

`tests/unit/routes/` SHALL NOT exist; route render belongs to
`integration`.

#### Scenario: Each lane reports its own runtime budget

- **GIVEN** the developer runs `pnpm test:run --project=unit`
- **THEN** the run SHALL exit successfully with no MSW lifecycle
  log line emitted, because the unit project does not start
  `setupServer`

#### Scenario: A route render test placed under `tests/unit/` fails the layout check

- **GIVEN** a contributor adds `tests/unit/routes/sales.test.tsx`
  that imports `createFileRoute`
- **WHEN** `pnpm test:layout` runs (`apps/web/scripts/check-test-layout.mjs`)
- **THEN** the check SHALL fail with a message naming the
  forbidden import and pointing to
  `tests/integration/routes/sales.spec.tsx` as the correct home

### Requirement: Vitest is configured with named projects `unit` and `integration`

`apps/web/vite.config.ts` SHALL declare two
[Vitest projects](https://vitest.dev/guide/projects) named `unit`
and `integration`. Each project SHALL configure:

- `include` rooted at its own subtree (`tests/unit/**/*.test.*`
  and `tests/integration/**/*.spec.*` respectively).
- `setupFiles` — the unit project loads `tests/setup.ts` only; the
  integration project additionally loads
  `tests/integration/setup.ts` which calls `server.listen()`
  before all, `server.resetHandlers()` after each, and
  `server.close()` after all per the
  [MSW Node integration guide](https://mswjs.io/docs/integrations/node).
- `testTimeout` — bounded per lane (unit fast, integration
  generous).

A run with no `--project` flag SHALL execute both projects and
merge coverage into a single report.

#### Scenario: MSW lifecycle hooks fire only for the integration project

- **WHEN** `pnpm test:run --project=unit` is invoked
- **THEN** `server.listen` SHALL NOT be invoked

- **WHEN** `pnpm test:run --project=integration` is invoked
- **THEN** `server.listen` SHALL be invoked exactly once before
  the first test and `server.close` SHALL be invoked once after
  the last test

### Requirement: MSW handlers are typed against the committed OpenAPI schema

The directory `apps/web/tests/integration/msw/` SHALL contain:

- `server.ts` — calls `setupServer(...handlers)` from `msw/node`.
- `handlers.ts` — declares the default handlers using
  `createOpenApiHttp<paths>({ baseUrl: ... })` where `paths` is
  the named export from `@/api/schema`.

A contributor SHALL NOT mock `openapi-fetch` directly in
integration tests. Per-test overrides SHALL use
`server.use(http.get(...))` with the typed `http` factory.

#### Scenario: A handler returning a renamed field fails `pnpm typecheck`

- **GIVEN** a backend schema regen renames `display_name` to
  `displayName` in `src/api/schema.d.ts`
- **GIVEN** an integration handler still returns
  `{ display_name: "Ada" }`
- **WHEN** `pnpm typecheck` runs in CI
- **THEN** the type-check SHALL fail at the handler file with a
  TypeScript error pointing at the unknown property

#### Scenario: A test overrides a handler using the typed factory

- **GIVEN** an integration spec for `/login`
- **WHEN** the spec calls
  `server.use(http.post("/v1/auth/login", ({response}) => response(401).json({...})))`
- **THEN** the override SHALL type-check against the schema and
  SHALL apply only to the test that registered it, because
  `resetHandlers` runs in the `afterEach` hook

### Requirement: Every route, hook, schema, and shared module has at least one verifying test

The change introduces a generated artefact
`apps/web/coverage/verification-matrix.json` whose keys enumerate
every entry of the SPA inventory:

- Every file under `src/routes/**/*.tsx`.
- Every exported hook from `src/features/{auth,tenants}/api/hooks.ts`.
- Every exported Zod schema from `src/features/{auth,tenants}/schemas/`.
- Every shared infra module under `src/api/` (excluding the
  generated `schema.d.ts`), `src/lib/`, and the shared component
  trees `components/{app-shell,app-sidebar,identity-layout}` plus
  the standalone widgets (`account-menu`, `brand-header`,
  `theme-provider`, `theme-toggle`, `logo`).
- Every feature component under
  `src/features/{auth,tenants,dashboard}/components/`.

For every key the value SHALL be a non-empty array of test file
paths. The matrix is regenerated by
`apps/web/scripts/verification-matrix.mjs` and the script SHALL
exit non-zero when any key has an empty value array.

#### Scenario: Removing the only test for `useSwitchTenantMutation` breaks the matrix gate

- **GIVEN** `useSwitchTenantMutation` is currently covered only by
  `tests/integration/features/tenants/api/hooks.spec.tsx`
- **WHEN** a PR deletes that file without adding a replacement
- **THEN** `pnpm test:matrix` SHALL exit non-zero, and the
  failure output SHALL identify the hook name

#### Scenario: Adding a new hook without a test breaks the matrix gate

- **GIVEN** a contributor adds
  `useArchiveTenantMutation` to
  `features/tenants/api/hooks.ts`
- **WHEN** `pnpm test:matrix` runs without an accompanying
  integration spec
- **THEN** the matrix script SHALL exit non-zero and name the
  missing hook

### Requirement: Playwright runs against a real backend in CI

When `PLAYWRIGHT_NO_WEBSERVER=1` is set in the environment,
`apps/web/playwright.config.ts` SHALL skip the embedded
`webServer` block; CI uses this escape hatch to point Playwright
at a stack started by `make` recipes (Postgres + API + SPA), so
e2e specs exercise the actual `/v1/*` contract, not the dev
server in isolation. Locally, the dev loop continues to support
`reuseExistingServer: true` against a developer-launched stack.

#### Scenario: A backend contract regression surfaces in the e2e job

- **GIVEN** the backend renames `POST /v1/tenants` request body
  field `legal_name` to `legalName` without updating the SPA
- **WHEN** the CI Playwright e2e job runs the
  `tenant-onboarding.spec.ts` spec against the real backend
- **THEN** the spec SHALL fail at the form submission step with a
  visible error captured in the trace artefact

### Requirement: Playwright specs are tagged `@smoke` or `@critical`

Every Playwright spec under `apps/web/tests/e2e/` SHALL declare
exactly one of the tags `@smoke` (must pass on every PR) or
`@critical` (runs on the nightly Chromium + WebKit cron). The
`apps/web/playwright.config.ts` projects SHALL configure
[`grep`](https://playwright.dev/docs/api/class-testproject#test-project-grep)
to select the tag matching the current CI job.

The `@smoke` set SHALL include at minimum:

- `auth.spec.ts` (login page renders).
- `health.spec.ts` (unauthenticated `/health`).
- `tenant-onboarding.spec.ts` (first-tenant creation entry).
- `dashboard-empty-state.spec.ts` (anonymous redirect from
  `/dashboard`).

The `@critical` set SHALL include at minimum:

- `member-management.spec.ts`.
- `permission-gating.spec.ts`.
- `rls-isolation.spec.ts`.

#### Scenario: PR CI job runs only smoke

- **WHEN** the `e2e-smoke` job in `web-checks.yml` runs
- **THEN** Playwright SHALL only execute specs tagged `@smoke`

### Requirement: Production diffs introduced by triad work SHALL be limited to `data-testid` annotations

Production code under `apps/web/src/` may only receive
`data-testid` attribute additions when adding or migrating tests
within this capability. Business-logic edits, styling changes, and
refactors MUST NOT be included.

#### Scenario: A non-test-id diff in `apps/web/src/` blocks the PR

- **GIVEN** a PR within this scope that modifies a `useEffect`
  body in `apps/web/src/features/tenants/api/hooks.ts`
- **WHEN** the change is reviewed
- **THEN** the reviewer SHALL block the PR and direct the diff to
  the appropriate feature sprint
