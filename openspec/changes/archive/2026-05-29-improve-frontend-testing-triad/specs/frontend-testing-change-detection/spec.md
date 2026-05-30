## ADDED Requirements

### Requirement: Per-glob coverage thresholds gate `features/`, `components/`, `lib/`, and `api/`

`apps/web/vite.config.ts` SHALL configure
[vitest `coverage.thresholds`](https://vitest.dev/config/#coverage-thresholds)
with the glob form, scoping per-tree minima:

- `src/features/auth/**`, `src/features/tenants/**`,
  `src/features/dashboard/**` — each glob SHALL declare its own
  `lines` and `branches` thresholds.
- `src/components/app-shell/**`,
  `src/components/app-sidebar/**` — same shape.
- `src/lib/**` — pure helpers; thresholds SHALL be the highest
  in the file (`lines: 90, branches: 80` floor).
- `src/api/!(schema.d.ts)` — runtime API helpers; `schema.d.ts`
  is excluded because it is generated.

`coverage.thresholds.perFile` SHALL remain `false` so the gate
runs over each glob aggregate; this makes failures name the glob,
not a single file.

`coverage.thresholds.autoUpdate` SHALL be configured with a
floor function `(n) => Math.floor(n)` so a maintainer running
`pnpm test:run --coverage --update-thresholds` ratchets every
glob to its measured floor, never lowers it, and never includes
decimals that flake on the next run.

#### Scenario: Removing a test that uniquely covers `features/tenants` fails the gate

- **GIVEN** the suite is green and `features/tenants` aggregate
  coverage is at the configured `lines` threshold
- **WHEN** a contributor deletes a test that uniquely covered ~20
  lines in `features/tenants/api/hooks.ts`
- **THEN** `pnpm test:run --coverage` SHALL exit non-zero and the
  failure SHALL name the glob `src/features/tenants/**` and the
  configured threshold

#### Scenario: Adding twenty uncovered lines under `bootstrap/` does not move the gate

- **GIVEN** a contributor adds twenty uncovered lines in
  `apps/web/src/app.tsx`
- **WHEN** `pnpm test:run --coverage` runs
- **THEN** the gate SHALL still pass because `app.tsx` is outside
  every configured glob — the gates target high-bug-density
  code, not generated or top-level glue

### Requirement: PR coverage may not regress against the base branch

A CI job named `coverage-delta` SHALL run on every PR. The job
SHALL:

1. Restore (or compute) `coverage/coverage-summary.json` for the
   base commit (`main` HEAD at PR open or last update).
2. Compute the same summary for the PR head.
3. For every gated glob declared in `vite.config.ts`,
   `head.lines - base.lines` and
   `head.branches - base.branches` SHALL be `>= 0`. Any negative
   delta fails the job.
4. The failure output SHALL print a table with `glob, base, head,
   delta` for the offending globs.

The base summary SHALL be cached via
[`actions/cache`](https://github.com/actions/cache) keyed on the
base commit SHA so the base run is paid once per `main` commit.

#### Scenario: A PR shipping a feature with no tests is rejected

- **GIVEN** a PR adds a 60-line component in
  `src/features/tenants/components/ArchiveDialog.tsx` and zero
  tests
- **WHEN** `coverage-delta` runs
- **THEN** the job SHALL fail with the offending glob
  `src/features/tenants/**` and a negative delta, even if the
  per-glob threshold is still satisfied in aggregate

#### Scenario: Refactors that move covered code are not penalised

- **GIVEN** a PR moves the body of `useLoginMutation` into a
  helper that is unit-tested via a new file
- **WHEN** `coverage-delta` runs and aggregate
  coverage is unchanged within rounding
- **THEN** the job SHALL pass

### Requirement: Every integration spec asserts accessibility via `axe-core`

The integration setup SHALL register a `vitest-axe` matcher (or
equivalent thin wrapper around `axe-core`). Every spec under
`tests/integration/` whose subject is a full route or a screen
SHALL include at least one assertion of the form:

```ts
expect(await axe(container)).toHaveNoViolations();
```

The rule set SHALL be `wcag2a` + `wcag2aa`. The allow-list of
known violations SHALL start empty; adding to it requires a
review with documented rationale in the test file.

#### Scenario: A new violation introduced by a route change fails the spec

- **GIVEN** a contributor removes the `aria-label` from a
  required form field in `routes/tenants/new.tsx`
- **WHEN** the integration spec runs
- **THEN** `expect(await axe(container)).toHaveNoViolations()`
  SHALL fail, naming the missing label rule

### Requirement: The verification matrix is uploaded as a CI artefact on every PR

The `coverage-delta` job (or a sibling
`verification-matrix` step) SHALL upload
`apps/web/coverage/verification-matrix.json` and
`apps/web/coverage/lcov-report/` as workflow artefacts. The
matrix file SHALL be human-readable JSON keyed by route/hook/
schema/component name with the test file paths that cover each.

#### Scenario: The matrix is downloadable from any PR run page

- **WHEN** the PR's `web-checks.yml` workflow finishes
- **THEN** the run page SHALL list a `verification-matrix`
  artefact whose payload, when opened, lists every inventory
  entry from `proposal.md` with at least one test file

### Requirement: `web-checks.yml` exposes the four lanes as distinct jobs

The workflow `.github/workflows/web-checks.yml` SHALL declare at
minimum four jobs: `unit`, `integration`, `e2e-smoke`, and
`coverage-delta`. `unit` and `integration` SHALL run in parallel.
`e2e-smoke` SHALL wait on neither but SHALL boot the real
backend per the triad spec. `coverage-delta` SHALL depend on
`unit` and `integration` completing so it can read both
projects' merged summaries.

#### Scenario: A failed `e2e-smoke` is reportable independently of `unit`

- **GIVEN** a PR that breaks the dashboard route but leaves
  unit tests green
- **WHEN** the workflow runs
- **THEN** the `e2e-smoke` job SHALL fail and the `unit` job
  SHALL pass — the failure surface SHALL identify the e2e job
  on the PR check list

### Requirement: A nightly cron exercises `@critical` Playwright specs on Chromium + WebKit

A scheduled GitHub Actions workflow SHALL run nightly (UTC), boot
the real backend stack, and execute Playwright with
`--grep @critical` against both Chromium and WebKit projects.
Failures SHALL open or update a GitHub Issue labelled
`flaky-e2e` (or `broken-e2e` when failure persists for two
consecutive runs) so silent regressions cannot accumulate.

#### Scenario: A WebKit-only regression surfaces within 24 hours

- **GIVEN** a PR introduces a CSS bug that breaks the
  `permission-gating` flow on Safari only
- **WHEN** the nightly job runs
- **THEN** the WebKit `@critical` run SHALL fail and an issue
  SHALL be opened (or refreshed) with the failing trace
  attached
