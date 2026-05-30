# frontend-testing-change-detection Specification

## Purpose

The triad lane structure (unit / integration / e2e) prevents tests
from sitting at the wrong layer. The change-detection gates make
the layered suite actually surface regressions on every PR. Three
gates collaborate: per-glob coverage thresholds keep the floor where
bug density is high; a coverage-delta job rejects PRs that lower
aggregate coverage on `main`; a verification matrix uploaded as a CI
artefact answers "is feature X tested?" without spelunking the
suite. The result is a workflow where shipping a new feature
without a covering test is a CI failure regardless of the absolute
coverage number.

## Requirements

### Requirement: Coverage thresholds gate the high-value source trees

`apps/web/vite.config.ts` SHALL configure
[vitest `coverage.thresholds`](https://vitest.dev/config/#coverage-thresholds)
scoped to the source trees where bugs hurt:

- Coverage is collected over `src/features/**/*.{ts,tsx}`,
  `src/components/**/*.{ts,tsx}`, `src/lib/**/*.{ts,tsx}`, and
  `src/api/**/*.{ts,tsx}` (excluding the generated
  `src/api/schema.d.ts`).
- Thresholds (`lines`, `branches`, `statements`, `functions`)
  SHALL be set at or below the measured floor of the latest green
  `main` run. Adding new untested code in the gated trees SHALL
  cause `pnpm test:run --coverage` to exit non-zero when the
  measured percentage drops below the configured floor.

`coverage.thresholds.perFile` SHALL remain `false` so the gate
runs over the configured glob aggregate. `autoUpdate` SHALL remain
`false` for CI runs; ratcheting the floor SHALL happen only via
the maintainer recipe documented in
`apps/web/tests/integration/README.md`.

#### Scenario: Removing a test that uniquely covers `features/tenants` fails the gate

- **GIVEN** the suite is green and aggregate coverage is at the
  configured `lines` threshold
- **WHEN** a contributor deletes a test that uniquely covered
  ~20 lines in `features/tenants/api/hooks.ts`
- **THEN** `pnpm test:run --coverage` SHALL exit non-zero with a
  threshold violation referencing the configured floor

#### Scenario: Adding uncovered lines outside the gated trees does not move the gate

- **GIVEN** a contributor adds twenty uncovered lines in
  `apps/web/src/app.tsx`
- **WHEN** `pnpm test:run --coverage` runs
- **THEN** the gate SHALL still pass because `app.tsx` is outside
  every configured glob

### Requirement: PR coverage may not regress against the base branch

A CI job named `coverage-delta` SHALL run on every pull request.
The job SHALL:

1. Restore (or compute) `coverage/coverage-summary.json` for the
   base commit (`main` HEAD when the PR was opened or last
   updated).
2. Compute the same summary for the PR head.
3. Diff the two via `apps/web/scripts/coverage-delta.mjs`. The
   script SHALL exit non-zero when aggregate `lines` or
   `branches` drop relative to the base.
4. The failure output SHALL print a table with
   `metric, base, head, delta` for the offending metrics.

The base summary SHALL be cached via
[`actions/cache`](https://github.com/actions/cache) keyed on the
base commit SHA so the base run is paid once per `main` commit.

#### Scenario: A PR shipping a feature with no tests is rejected

- **GIVEN** a PR adds a 60-line component in
  `src/features/tenants/components/ArchiveDialog.tsx` and zero
  tests
- **WHEN** `coverage-delta` runs
- **THEN** the job SHALL fail with the offending metric (lines)
  showing a negative delta

#### Scenario: Refactors that move covered code are not penalised

- **GIVEN** a PR moves the body of `useLoginMutation` into a
  helper that is unit-tested via a new file
- **WHEN** `coverage-delta` runs and aggregate coverage is
  unchanged within rounding
- **THEN** the job SHALL pass

### Requirement: Integration specs MAY assert accessibility via `axe-core`

The integration lane provides a shared helper
`tests/integration/_support/expectNoA11yViolations.ts` that wraps
`axe-core` with the `wcag2a` + `wcag2aa` rule set. Integration
specs whose subject is a full route or screen SHOULD call
`expectNoA11yViolations(container)` against the rendered DOM.

When called, the helper SHALL throw with a list of violation ids
and impact levels if any are found. The allow-list of known
violations SHALL start empty; adding to it requires a review
comment in the test file documenting the rationale.

#### Scenario: A new violation introduced by a route change fails the spec

- **GIVEN** a route spec that calls
  `await expectNoA11yViolations(container)` on the rendered
  output
- **WHEN** a contributor removes the `aria-label` from a required
  form field
- **THEN** the helper SHALL throw and the spec SHALL fail with
  the missing-label rule named in the error message

### Requirement: The verification matrix is uploaded as a CI artefact on every PR

The `integration` CI job SHALL upload
`apps/web/coverage/verification-matrix.json` and the
`apps/web/coverage/lcov-report/` directory as workflow artefacts.
The matrix file SHALL be human-readable JSON keyed by
`route:`/`hook:`/`schema:`/`infra:`/`component:` prefixes with the
test file paths that cover each.

#### Scenario: The matrix is downloadable from any PR run page

- **WHEN** the PR's `web-checks.yml` workflow finishes
- **THEN** the run page SHALL list a `verification-matrix`
  artefact whose payload, when opened, lists every inventory
  entry with at least one test file

### Requirement: `web-checks.yml` exposes the four lanes as distinct jobs

The workflow `.github/workflows/web-checks.yml` SHALL declare at
minimum four jobs: `unit`, `integration`, `e2e-smoke`, and
`coverage-delta`. `unit` and `integration` SHALL run in parallel.
`e2e-smoke` SHALL run independently. `coverage-delta` SHALL run
on `pull_request` events and depend on `unit` and `integration`.

#### Scenario: A failed `e2e-smoke` is reportable independently of `unit`

- **GIVEN** a PR that breaks the dashboard route but leaves unit
  tests green
- **WHEN** the workflow runs
- **THEN** the `e2e-smoke` job SHALL fail and the `unit` job
  SHALL pass — the failure surface SHALL identify the e2e job on
  the PR check list

### Requirement: A nightly cron exercises `@critical` Playwright specs on Chromium + WebKit

A scheduled GitHub Actions workflow `.github/workflows/web-e2e-nightly.yml`
SHALL run nightly (UTC), and execute Playwright with
`--project=critical --project=webkit` selecting `@critical` specs.
Failures SHALL upload the Playwright report as an artefact for
inspection.

#### Scenario: A WebKit-only regression surfaces within 24 hours

- **GIVEN** a PR introduces a CSS bug that breaks the
  `permission-gating` flow on Safari only
- **WHEN** the nightly job runs
- **THEN** the WebKit `@critical` run SHALL fail and the
  Playwright report artefact SHALL be available on the workflow
  run page
