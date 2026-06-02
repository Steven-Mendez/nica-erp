# e2e-tooling Specification

## Purpose
TBD - created by archiving change test-backfill-and-e2e-tooling. Update Purpose after archive.
## Requirements
### Requirement: Playwright is the frontend end-to-end test runner

The `apps/web/` package SHALL declare `@playwright/test` as a
devDependency. The repository SHALL contain a top-level
`apps/web/playwright.config.ts` exposing at minimum two projects
named `chromium` and `webkit`, a `webServer` block that brings up
the SPA against a local development server, and a configurable
`baseURL` honouring the `PLAYWRIGHT_BASE_URL` environment variable.
In CI the `webServer.reuseExistingServer` SHALL be `false` so each
job starts from a clean process.

#### Scenario: `npm run test:e2e` runs the Chromium project from a clean clone

- **GIVEN** a fresh clone of the repository on a Linux runner with
  Node.js and pnpm installed
- **WHEN** `pnpm install && pnpm --filter web exec playwright install --with-deps chromium && pnpm --filter web run test:e2e -- --project=chromium` is executed
- **THEN** the command SHALL succeed and the Playwright HTML report
  SHALL be written to `apps/web/playwright-report/`

#### Scenario: WebKit is configured but warning-only

- **WHEN** the Playwright CI job runs
- **THEN** the Chromium project failures SHALL fail the job
- **AND** WebKit project failures SHALL be reported as a warning
  annotation without failing the job

### Requirement: Playwright fixtures encapsulate UI-driven auth and tenant setup

The repository SHALL contain `apps/web/tests/e2e/fixtures/auth.ts`
exposing two helpers:

- `signupConfirmAndLogin(page, { email, password })` SHALL drive
  the `/signup`, `/confirm`, and `/login` flows end-to-end against
  the SPA, returning once the SPA has navigated to its
  post-login route.
- `loginAs(page, { email, password })` SHALL drive the `/login`
  flow only, assuming the user already exists.

A second module `apps/web/tests/e2e/fixtures/tenant.ts` SHALL
expose `createTenant(page, fixtureData)` that drives the existing
`/tenants/new` form end-to-end. None of the fixtures SHALL bypass
the SPA by calling the API directly.

#### Scenario: Fixtures fail loudly when the underlying form changes

- **GIVEN** a regression that removes the email input from `/signup`
- **WHEN** `signupConfirmAndLogin` is invoked
- **THEN** the fixture SHALL fail in the signup step with a
  Playwright selector error, not silently fall back to an API call

### Requirement: Playwright suite covers the five sprint-03 happy paths

The directory `apps/web/tests/e2e/` SHALL contain at minimum the
following specs:

- `auth.spec.ts` — sign up, confirm, log in, and verify the
  `/account` screen reflects the registered profile data.
- `tenant-onboarding.spec.ts` — create the first tenant for a
  freshly registered user, switch into it, and land on
  `/dashboard`.
- `member-management.spec.ts` — admin invites a second user in
  one browser context; the invitee accepts via the deep link in
  a second browser context; both contexts see the new member in
  the list; the admin then removes the member.
- `permission-gating.spec.ts` — a user with role `viewer` and a
  user with role `admin` see different affordances (buttons,
  forms) on `/tenants/$id/members`.
- `rls-isolation.spec.ts` — two simultaneous browser contexts
  signed into two distinct tenants. Neither context observes any
  resource belonging to the other tenant through the SPA.

#### Scenario: All five specs are green on Chromium

- **WHEN** `pnpm --filter web run test:e2e -- --project=chromium` is
  executed
- **THEN** all five specs SHALL be in the passing set with no
  retries

### Requirement: CI uploads Playwright artifacts on failure

The repository SHALL contain a GitHub Actions workflow step that,
when the Playwright job fails, uploads the directories
`apps/web/playwright-report/` and `apps/web/test-results/` as
workflow artifacts named `playwright-report` and
`playwright-traces` respectively.

#### Scenario: A failing Playwright run yields traces in the workflow run page

- **GIVEN** a deliberate `expect(...).toBeTruthy()` failure in
  `tests/e2e/auth.spec.ts`
- **WHEN** the CI workflow runs against the introducing PR
- **THEN** the workflow run page SHALL list a `playwright-report`
  artifact whose `index.html` opens to a failing test entry with
  attached screenshot and trace

### Requirement: Production diffs in this change SHALL be limited to test-selector annotations

Production code under `apps/api/src/` and `apps/web/src/` SHALL only receive `data-testid` attribute additions (or equivalent test selectors) within the scope of this change. Business logic edits, styling changes, and refactors MUST NOT be included.

#### Scenario: A non-test-id diff in `apps/web/src/` blocks the PR

- **GIVEN** a PR within this change that modifies a
  `useEffect` body in `apps/web/src/features/tenants/api/hooks.ts`
- **WHEN** the change is reviewed
- **THEN** the reviewer SHALL block the PR and direct the diff to
  sprint 3.6 (`welcome-onboarding-rename-members`)

