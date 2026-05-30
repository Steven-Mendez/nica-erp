## Context

This change stacks on top of
[`test-backfill-and-e2e-tooling`](../test-backfill-and-e2e-tooling/proposal.md)
and the feature-slice frontend laid down by
[`add-frontend-dashboard-shell`](../add-frontend-dashboard-shell/proposal.md)
and follow-up work
([`improve-tenants-new-form`](../improve-tenants-new-form/proposal.md),
[`restructure-sidebar-empresa-and-account`](../restructure-sidebar-empresa-and-account/proposal.md),
[`simplify-creation-and-empresa-rebrand`](../simplify-creation-and-empresa-rebrand/proposal.md)).

The architectural envelope is fixed by:

- [docs/14-testing.md](../../../docs/14-testing.md) — the triad
  baseline (currently backend-centric; this change extends the
  "Frontend tests" section).
- [docs/09-frontend.md](../../../docs/09-frontend.md) — feature-slice
  layout and the four rules per
  [[project_frontend_not_hexagonal]] and
  [[project_frontend_slice_layout]].
- [ADR-0025](../../../docs/adr/0025-testing-strategy.md) — strategy
  commitments.
- [[feedback_test_layout]] — tests under
  `apps/web/tests/{unit,integration,e2e}/` mirroring `src/`, never
  co-located.

The change is **test-only**: production code under `apps/web/src/`
may only gain `data-testid` attributes. The design surface is
*tooling* (vitest projects, MSW + `openapi-msw`, `vitest-axe`,
Playwright real-backend mode), *layout* (the three-lane tree), and
*gates* (per-PR coverage delta, type-safe contract handlers, axe
matcher).

## Goals / Non-Goals

**Goals**

- Three named lanes — `unit`, `integration`, `e2e` — each with a
  clear ownership boundary (see "Decision 1") and a clear failure
  mode (which class of bug it catches).
- A verification matrix `apps/web/coverage/verification-matrix.json`
  that lists every route, hook, schema, and shared component and
  the tests that cover them. The matrix is regenerated on every
  `make test-fe-all` run.
- A PR cannot regress the matrix: removing a test that was the only
  thing exercising a hook/route/schema fails the
  `verification-matrix` CI step.
- MSW handlers are typed against `src/api/schema.d.ts` via
  `openapi-msw`. A backend rename surfaces as a TypeScript error in
  `pnpm typecheck`, not a green test against a stale shape.
- E2E runs against a real backend (Postgres + API + SPA) in CI, not
  the dev server in isolation.
- Coverage delta gate fails the PR if `lines` or `branches` on
  `features/` or `components/` drop relative to `main`.
- Every integration spec exercises `axe-core`; new WCAG A/AA
  violations fail the build.

**Non-Goals**

- No visual regression / screenshot diffing.
- No mutation testing (Stryker), no property-based testing
  (`fast-check`). Deferred until a recurring bug class motivates them.
- No third-party coverage host. Delta gate lives in-workflow.
- No backend test changes.
- No new product behaviour. Only `data-testid` annotations on
  existing components.
- No replacement of the existing
  `test-backfill-and-e2e-tooling.test-coverage` spec. The two
  capabilities coexist; this change introduces *additional* gates
  and *additional* layout rules, not replacements.

## Decisions

### 1. Three lanes with explicit ownership

| Lane | Where | Owns | Forbidden |
|---|---|---|---|
| `unit` | `apps/web/tests/unit/` | Pure logic: Zod schemas, `lib/*` helpers, isolated reducers (`sidebar-context`), pure pure-function components, `api/queryKeys`, `api/tokenStore`, `api/useHasPermission` logic. No `QueryClient`, no router, no MSW. | Anything that imports `useQuery`/`useMutation`/`createRoute` in the System Under Test. |
| `integration` | `apps/web/tests/integration/` | A route or feature flow rendered with the **real** `<RouterProvider>` + a fresh `<QueryClientProvider>` + an MSW server typed via `openapi-msw`. Asserts request shape, response handling, error UI, redirects, and axe-clean DOM. | Mocking `openapi-fetch` directly. Stubbing `react-router`. Bypassing the form to call hooks ad-hoc. |
| `e2e` | `apps/web/tests/e2e/` | Playwright against a real backend (Postgres + API + SPA), per the canonical user journeys. Drives the SPA the way a user would. | API shortcuts in fixtures (e.g. POSTing to `/v1/login`). Mocking. Selectors brittle to copy changes (prefer roles/labels; `data-testid` last). |

Rationale: the prior change conflated route render tests with unit
tests (they all live under `tests/unit/routes/`). A route render
test exercises React Query, TanStack Router, and form state — it
*is* an integration test by every textbook definition. Calling it
"unit" gives a false sense of where the coverage sits and obscures
which class of regression a failure points to.

### 2. MSW with `openapi-msw` is the integration boundary

Decision: integration tests do not mock `openapi-fetch`. They mock
the HTTP layer with MSW handlers built via
`createOpenApiHttp<paths>()` where `paths` is the type imported
from the committed `src/api/schema.d.ts`. The
[`openapi-msw` README](https://github.com/christoph-fricke/openapi-msw)
shows the pattern verbatim.

```ts
// apps/web/tests/integration/msw/handlers.ts
import { createOpenApiHttp } from "openapi-msw";
import type { paths } from "@/api/schema";

export const http = createOpenApiHttp<paths>({ baseUrl: "/v1" });
```

Rationale: a hand-written mock for `/v1/me` keeps passing after the
backend renames `displayName` to `display_name`. With `openapi-msw`,
the handler returning the old key is a TypeScript error in
`pnpm typecheck`, which is already a merge gate. Contract drift
becomes visible at compile time, not at the point a user clicks
the broken form in production.

Rejected alternative: hand-rolled MSW handlers, then a runtime
contract assertion against the committed schema. Adds a second
source of truth and a runtime cost; the type system already does
the job.

### 3. Vitest projects split the run, not the include glob

Decision: `apps/web/vite.config.ts` uses the
[Vitest `projects`](https://vitest.dev/guide/projects) feature to
expose two named projects `unit` and `integration`, each with its
own `setupFiles` and `include`. A run with no `--project` runs
both; CI selects one explicitly in each job. Coverage merges the
two when `--coverage` is set.

Rationale: two projects let each lane have its own setup (MSW
`server.listen()` only for integration) and its own runtime budget
(`testTimeout: 250` for unit, `1000` for integration). A single
glob with both kinds intermixed forces every test to pay the MSW
startup cost.

### 4. Per-file thresholds for `features/` and `components/`

Decision: use vitest's documented glob-form thresholds — for
example:

```ts
coverage: {
  thresholds: {
    autoUpdate: (n) => Math.floor(n),
    "src/features/auth/**": { lines: 80, branches: 70 },
    "src/features/tenants/**": { lines: 80, branches: 70 },
    "src/features/dashboard/**": { lines: 80, branches: 70 },
    "src/components/app-shell/**": { lines: 80, branches: 70 },
    "src/components/app-sidebar/**": { lines: 80, branches: 70 },
    "src/lib/**": { lines: 90, branches: 80 },
    "src/api/!(schema.d.ts)": { lines: 85, branches: 70 },
  },
},
```

The exact numbers are the ratchet target; the ratchet starts at the
measured baseline and `autoUpdate: Math.floor` raises it as the
backfill lands, per the
[Vitest auto-update docs](https://vitest.dev/config/#coverage-thresholds-autoupdate).
`perFile: false` keeps the aggregate over the glob (not per file)
so a single low-coverage file is reported by name rather than
silently averaged.

Rationale: a single aggregate gate (today's
`lines: 5, functions: 25`) is satisfied by adding any test, even
to a trivial helper. Glob-scoped thresholds keep the bar where the
bugs hurt (`features/` business logic), tolerant where they don't
(`api/schema.d.ts` is auto-generated).

### 5. Per-PR coverage delta gate

Decision: the `web-checks.yml` workflow has a `coverage-delta` job
that:

1. Checks out `main`, runs `pnpm test:run --coverage` against it,
   captures `coverage/coverage-summary.json`.
2. Checks out the PR head, runs the same, captures the second
   summary.
3. Computes `delta = head.lines - base.lines` over the gated globs
   and fails when `delta < 0`.

The job uses
[`actions/cache`](https://github.com/actions/cache) keyed on the
base commit SHA so the base run is paid once per main commit.

Rationale: thresholds keep the floor; the delta keeps the
direction. Together they make "a PR that ships a new feature
without tests" a CI failure regardless of the absolute number.

### 6. Verification matrix is generated, not maintained by hand

Decision: a small Node script
`apps/web/scripts/verification-matrix.mjs` walks `src/` and emits
`coverage/verification-matrix.json`. For every route, hook,
schema, and shared component it lists the test files that import
the module (resolved via `tsc --traceResolution` cached output).
A second pass cross-checks the inventory in `proposal.md` (route
list + hook list + schema list) and fails if any inventory entry
maps to zero tests.

Rationale: a human-maintained list rots. A generated list keeps
itself honest and the inventory in the proposal becomes the
single source of truth. The script runs in
`make test-fe-all` and the artefact is uploaded by CI so the
"what is verified" answer is one click away from any PR run page.

### 7. Playwright runs against a real backend in CI

Decision: `apps/web/playwright.config.ts` keeps
`webServer: pnpm dev` for the local dev loop (with
`reuseExistingServer: true`). In CI, the workflow boots the stack
via the existing `make` recipes (Postgres testcontainer, API,
SPA) and sets `PLAYWRIGHT_BASE_URL` accordingly; `webServer` is
removed from the config in that mode via the
`PLAYWRIGHT_NO_WEBSERVER=1` escape.

Rationale: today's Playwright spec hits the dev server with no
API. That catches layout bugs and nothing else. The whole point
of the e2e tier is to detect contract drift between the SPA and
the API — that requires a real API process.

### 8. Tag-based Playwright selection

Decision: Playwright specs use `@smoke` and `@critical` tags. CI
gates use `--grep` per the
[Playwright project grep docs](https://playwright.dev/docs/test-annotations#tag-tests):

- PR jobs run `--grep @smoke` (auth, tenant onboarding,
  dashboard-empty-state). Target runtime ≤ 90 s.
- A nightly cron runs `--grep @critical` (member management,
  permission gating, rls isolation, cross-tenant) on Chromium and
  WebKit.

Rationale: the goal "detect real problems every time something
changes" is in tension with "keep PR feedback under five minutes".
Tags resolve the tension: smoke for every PR, critical nightly.

### 9. Production diffs are `data-testid` only

Same constraint as
[`test-backfill-and-e2e-tooling`](../test-backfill-and-e2e-tooling/design.md)
decision 5, repeated here because the same reviewers will be
asked to enforce it on PRs against this change.

## Risks / Trade-offs

- **CI runtime grows ~4–6 minutes** when integration + coverage
  delta are added. Mitigation: integration project runs in
  `happy-dom` (no jsdom), and the delta gate caches the base run
  by commit SHA so it only re-runs on a new main.
- **MSW + `openapi-msw` dependency adds a TypeScript compile cost**
  in the test tree. Mitigation: the integration project has its
  own `tsconfig.json` extending the base so the IDE and the build
  share the cache.
- **Tagged Playwright suite risks "everything is critical, nothing
  is smoke"**. Mitigation: smoke = a regression breaks the
  app-shell or auth and the dev cannot proceed; critical = a
  regression breaks a flow that the user can recover from. The
  rule is documented in the integration suite README that this
  change adds.
- **Per-PR coverage diff can be noisy** when the baseline shifts
  due to flaky tests. Mitigation: the base run uses
  `--reporter=junit` and a re-run on failure; if the base is
  flaky, the PR is held until main is green.
- **`openapi-msw` is upstream of `openapi-typescript` v7**; the
  generated `schema.d.ts` must use the `paths` named export
  ([already the case in this repo](../../../apps/web/src/api/schema.d.ts)).
  Any future regen needs to keep the named export.

## Migration plan

1. Land the OpenSpec change (this artefact set). No code yet.
2. **Layout** — move the route render tests from
   `tests/unit/routes/` to `tests/integration/routes/`; rename
   `tests/unit/api/interceptor.test.ts` to remain unit (it tests
   the helper, not a round-trip); the round-trip moves to
   `tests/integration/api/interceptor.spec.ts`.
3. **MSW** — add devDependencies, scaffold
   `tests/integration/msw/{server,handlers}.ts`, port the
   existing route render tests to MSW one at a time. Each port
   is a separate PR; each PR explicitly references the route or
   feature it covers.
4. **Verification matrix script + inventory cross-check** — add
   the script, wire it into `make test-fe-all`, fail when any
   inventory entry has zero coverage.
5. **Quality gates** — per-glob thresholds first (no CI change),
   then `vitest-axe` matcher rollout (one slice at a time), then
   the coverage delta job.
6. **E2E real-backend mode** — update Playwright config and
   `web-checks.yml`. Backfill the four missing sprint-03 specs.
   Tag everything as `@smoke` or `@critical`.
7. **Doc update** — replace the "Frontend tests" section of
   `docs/14-testing.md`. Per
   [[feedback_doc_hierarchy]] / [[feedback_no_temporal_refs_in_comments]],
   the doc never references this OpenSpec change; it states the
   triad as the project standard.
8. **Closure** — append a closure note to the current sprint doc
   documenting the measured ratchet floor at landing.

## Open Questions

- **Threshold ratchet cadence**: do we ratchet on every PR or only
  on `main` after a green run? Decision deferred to the first
  ratchet PR; default is `main`-only.
- **Verification matrix granularity**: do we list every UI
  component (`button`, `input`, …) individually or only the ones
  that diverge from upstream shadcn? The proposal commits to the
  divergence-only approach; the script implements that filter.
- **Per-slice path filter scope**: today `web-checks.yml` runs the
  whole suite on any `apps/web/**` change. Switching to per-slice
  filters is a separate sprint topic if the suite ever exceeds
  ~5 minutes.

## References

- MSW + Vitest setup, `setupServer` lifecycle:
  [https://mswjs.io/docs/integrations/node](https://mswjs.io/docs/integrations/node)
- Type-safe handlers from OpenAPI:
  [https://github.com/christoph-fricke/openapi-msw](https://github.com/christoph-fricke/openapi-msw)
- Vitest coverage thresholds (glob + `autoUpdate`):
  [https://vitest.dev/config/#coverage-thresholds](https://vitest.dev/config/#coverage-thresholds)
- Vitest projects:
  [https://vitest.dev/guide/projects](https://vitest.dev/guide/projects)
- Playwright `grep` and sharding:
  [https://playwright.dev/docs/test-annotations#tag-tests](https://playwright.dev/docs/test-annotations#tag-tests)
  and
  [https://playwright.dev/docs/test-sharding](https://playwright.dev/docs/test-sharding)
- `axe-core` matcher for jest-dom-style assertions:
  [https://github.com/dequelabs/axe-core](https://github.com/dequelabs/axe-core)
