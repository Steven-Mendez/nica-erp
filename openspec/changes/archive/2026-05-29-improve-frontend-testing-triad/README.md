# improve-frontend-testing-triad

Frontend testing reorganised into three explicit lanes
(`tests/{unit,integration,e2e}`) with vitest projects, MSW + `openapi-msw`
type-safe handlers, a generated verification matrix that fails the build
if any inventory entry is uncovered, per-glob coverage thresholds,
a per-PR coverage delta gate, and Playwright `@smoke` / `@critical`
tags driving four CI jobs plus a nightly Chromium + WebKit cron.

Outcome at close: **193 tests green** (98 unit + 95 integration),
**87 inventory entries verified** (21 routes, 23 hooks, 11 schemas,
10 infra modules, 22 components), measured coverage floor
lines 82.79 / branches 80.88 / functions 67.41 / statements 82.79;
thresholds ratcheted to lines 80 / branches 78 / functions 65 /
statements 80 with a 2-point buffer.

Durable specs under
[`openspec/specs/frontend-testing-triad/spec.md`](../../../specs/frontend-testing-triad/spec.md)
and
[`openspec/specs/frontend-testing-change-detection/spec.md`](../../../specs/frontend-testing-change-detection/spec.md).

Open follow-ups carried to backlog (documented in `tasks.md`):

- Playwright real-backend fixtures
  (`tests/e2e/fixtures/{auth,tenant}.ts`); smoke and critical specs
  currently assert the entry surface only.
- Placeholder route integration specs (`__root`, `settings`,
  `sales`, `reports`, `inventory`, `empresa/settings`) — land with
  the sprint that ships their content.
- Route-by-route `expectNoA11yViolations` rollout (helper ships;
  call sites land incrementally).
