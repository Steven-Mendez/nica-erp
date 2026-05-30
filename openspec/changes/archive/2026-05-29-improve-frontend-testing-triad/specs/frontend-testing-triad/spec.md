## ADDED Requirements

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
- **WHEN** `pnpm lint` runs (or the dedicated
  `scripts/check-test-layout.mjs` invoked from CI)
- **THEN** the check SHALL fail with a message naming the
  forbidden import and pointing to
  `tests/integration/routes/sales.spec.tsx` as the correct home

### Requirement: Vitest is configured with named projects `unit` and `integration`

`apps/web/vite.config.ts` SHALL declare two
[Vitest projects](https://vitest.dev/guide/projects) named `unit`
and `integration`. Each project SHALL configure:

- `include` rooted at its own subtree (`tests/unit/**` and
  `tests/integration/**` respectively).
- `setupFiles` — the unit project loads `tests/setup.ts` only; the
  integration project additionally loads
  `tests/integration/setup.ts` which calls `server.listen()`
  before all, `server.resetHandlers()` after each, and
  `server.close()` after all per the
  [MSW Node integration guide](https://mswjs.io/docs/integrations/node).
- `testTimeout` — `250` ms for unit, `1000` ms for integration.

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
  `createOpenApiHttp<paths>({ baseUrl: "/v1" })` where `paths` is
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
  `server.use(http.post("/auth/login", () => response(401).json({ ... })))`
- **THEN** the override SHALL type-check against the schema and
  SHALL apply only to the test that registered it, because
  `resetHandlers` runs in the `afterEach` hook

### Requirement: Every route, hook, and schema in the inventory has at least one verifying test

The change introduces a generated artefact
`apps/web/coverage/verification-matrix.json` whose keys enumerate
every entry of the inventory committed to `proposal.md`:

- All 22 routes listed in `proposal.md` "Routes (22)".
- All 11 hooks under `features/auth/api/hooks.ts` and all 12
  hooks under `features/tenants/api/hooks.ts`.
- All 7 auth Zod schemas and all 4 tenants Zod schemas.
- All shared infra modules under `src/api/`,
  `src/lib/`, `src/components/app-shell/`,
  `src/components/app-sidebar/`, and the standalone shared
  components (`account-menu`, `brand-header`, `theme-provider`,
  `theme-toggle`, `identity-layout`).

For every key the value SHALL be a non-empty array of test file
paths. The matrix is regenerated by
`make test-fe-all` and the script SHALL exit non-zero when any
key has an empty value array.

#### Scenario: Removing the only test for `useSwitchTenantMutation` breaks the matrix gate

- **GIVEN** `useSwitchTenantMutation` is currently covered only by
  `tests/integration/features/tenants/api/switch-tenant.spec.tsx`
- **WHEN** a PR deletes that file without adding a replacement
- **THEN** `make test-fe-all` SHALL exit non-zero, and the
  failure output SHALL identify the hook name and the deleted
  test path

#### Scenario: Adding a new hook without a test breaks the matrix gate

- **GIVEN** a contributor adds
  `useArchiveTenantMutation` to
  `features/tenants/api/hooks.ts`
- **WHEN** `make test-fe-all` runs without an accompanying
  integration spec
- **THEN** the matrix script SHALL exit non-zero, name the
  missing hook, and suggest the conventional test path
  (`tests/integration/features/tenants/api/archive-tenant.spec.tsx`)

### Requirement: Playwright runs against a real backend in CI

The CI workflow that executes Playwright SHALL boot the real
backend stack (Postgres + API + SPA) before the run; the
`webServer` block in `apps/web/playwright.config.ts` SHALL be
disabled in CI via `PLAYWRIGHT_NO_WEBSERVER=1` (or equivalent),
and `PLAYWRIGHT_BASE_URL` SHALL point at the SPA fronted by the
real API.

Locally, the dev loop SHALL continue to support
`reuseExistingServer: true` against a developer-launched stack
for the fast iteration loop.

#### Scenario: A backend contract regression surfaces in the e2e job

- **GIVEN** the backend renames `POST /v1/tenants` request body
  field `legal_name` to `legalName` without updating the SPA
- **WHEN** the CI Playwright e2e job runs the
  `tenant-onboarding.spec.ts` spec
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

- `auth.spec.ts` (sign-up → confirm → log-in).
- `tenant-onboarding.spec.ts` (first tenant creation and switch).
- `dashboard-empty-state.spec.ts` (newly created empresa lands
  on a populated empty state).

The `@critical` set SHALL include at minimum:

- `member-management.spec.ts`.
- `permission-gating.spec.ts`.
- `rls-isolation.spec.ts`.

#### Scenario: PR CI job runs only smoke

- **WHEN** the `e2e-smoke` job in `web-checks.yml` runs
- **THEN** Playwright SHALL only execute specs tagged `@smoke`,
  and the job SHALL fail if any `@smoke` spec has no assertions

### Requirement: Production diffs in this change SHALL be limited to `data-testid` annotations

Production code under `apps/web/src/` may only receive
`data-testid` attribute additions within the scope of this
change. Business-logic edits, styling changes, and refactors
MUST NOT be included.

#### Scenario: A non-test-id diff in `apps/web/src/` blocks the PR

- **GIVEN** a PR within this change that modifies a `useEffect`
  body in `apps/web/src/features/tenants/api/hooks.ts`
- **WHEN** the change is reviewed
- **THEN** the reviewer SHALL block the PR and direct the diff to
  the appropriate feature sprint
