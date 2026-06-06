## Why

The Makefile currently exposes **twelve** test-related targets — one
per backend lane (`test-be-unit`, `test-be-integration`,
`test-be-e2e`), one per frontend lane (`test-fe-unit`,
`test-fe-integration`, `test-fe-e2e`), a frontend matrix check
(`test-fe-matrix`), two coverage gates (`test-be-coverage`,
`test-fe-coverage`), two aggregates (`test-fe-all`, `test-all`),
plus the lightweight `test` alias. Five of these are spec-locked
(`backend-test-quality-guards` names the three BE lanes by Makefile
target; `test-coverage` names both coverage gates by Makefile
target), so a Makefile cleanup that touches them is a spec-contract
change and cannot land via a pure refactor.

In day-to-day use the operator runs "everything" or "everything
except the slow e2e lane". The granular per-lane recipes are paid
for in `make help` noise and in spec verbosity without matching the
real invocation pattern. The matching CI workflows
(`api-checks.yml`, `web-checks.yml`) do **not** go through `make` —
they invoke `uv run pytest -m unit` and `pnpm test:unit` directly —
so the per-lane Makefile targets do not even serve as a CI parity
shim.

This change collapses the test surface to a single parametrized
`test` recipe driven by variables (`SCOPE`, `LANE`, `COV`) and
amends the two spec files so the requirements describe the new
invocation pattern instead of fixed target names.

## What Changes

- **Makefile (apps-wide, lives in `make/test.mk` after the split):**
  - **Removes** the five spec-named recipes (`test-be-unit`,
    `test-be-integration`, `test-be-e2e`, `test-be-coverage`,
    `test-fe-coverage`) along with the four non-spec aggregates
    (`test-fe-unit`, `test-fe-integration`, `test-fe-matrix`,
    `test-fe-all`, `test-all`). Net: 11 recipes removed.
  - **Keeps** `test` (now the canonical entrypoint) and
    `test-e2e-smoke` (Playwright is a separate runner; opt-in).
  - **Adds** the following variables to `test`:
    - `SCOPE=be|fe` — restrict to one stack (default: both).
    - `LANE=unit|integration|e2e` — pick a specific backend lane
      (default: all three). `LANE` is a no-op when `SCOPE=fe`
      because the frontend uses vitest project filtering, not
      directory-based lanes; `LANE=unit` on the frontend maps to
      `pnpm test:unit`, `LANE=integration` to `pnpm test:integration`.
    - `COV=1` — add coverage gates (90% backend trees, 80%
      frontend `features/` + `components/`) and the FE inventory
      matrix check; mirrors what `test-all` used to do.
- **`backend-test-quality-guards` spec:** the **Triad-respecting
  test lanes** requirement is modified so its three scenarios refer
  to `make test SCOPE=be LANE=<lane>` instead of the discrete
  `test-be-<lane>` recipes. All other requirements
  (property-based coverage, schema-vs-repository guard, RLS guard,
  shared factories, read-only use-case coverage) are unchanged
  because they describe **what** the suite asserts, not **how** the
  operator invokes it.
- **`test-coverage` spec:** the two "coverage gate" requirements
  are modified so they refer to `make test SCOPE=be COV=1` and
  `make test SCOPE=fe COV=1` respectively. The Sprint-03 RLS
  isolation gate requirement is modified so it refers to "the
  default `make test` invocation" instead of `make test-e2e` (the
  current spec name was never a real target). The tree-scoped
  threshold requirement is unchanged.
- **Documentation:** `docs/14-testing.md`, `docs/sprints/03-tenants-and-rls.md`
  (only the carry-over reference table, not the historical
  narrative), and `CONTRIBUTING.md` updated to use the parametrized
  form. The `docs/14-testing.md` "Cheat sheet" section explicitly
  spells out the `SCOPE` / `LANE` / `COV` matrix so contributors
  can find every previous invocation.

## Non-Goals

- **Coverage thresholds stay where they are** (89/90% on the three
  backend trees, 80% on FE `features/` + `components/`). Tightening
  thresholds is a separate change.
- **CI workflows are NOT touched.** `api-checks.yml` and
  `web-checks.yml` already invoke `pytest` / `pnpm` directly; they
  do not depend on Makefile target names. Their `pytest -m unit`
  and `pnpm test:unit` invocations stay as-is.
- **Playwright (`test-e2e-smoke`) stays a separate target** rather
  than folding into `make test E2E=1`. Playwright has its own
  runner, its own browser deps, its own marker (`@smoke`), and is
  meaningfully different in semantics from the vitest lanes. Hiding
  it behind a variable would make it less discoverable.
- **The FE inventory matrix check is not promoted to a top-level
  target.** It runs inside `make test COV=1` because the gate it
  enforces (every inventory entry has a covering test) is morally
  a coverage gate.
- **`makemigration` removal** (manual, no `--autogenerate`) is a
  sibling cleanup landing in the same PR but is NOT spec-locked,
  so it is not part of this change's deltas.

## Impact

- Affected code: `make/test.mk` (post-Makefile-split file that
  holds the test recipes), and the two spec files in
  `openspec/specs/`.
- Affected docs: `docs/14-testing.md`, `CONTRIBUTING.md`, the
  sprint-03 reference paragraph.
- Affected APIs: none.
- Affected CI: none (verified — `.github/workflows/api-checks.yml`
  and `web-checks.yml` invoke `pytest` / `pnpm` directly).
- Dependencies: none.
- Migration for contributors: a one-line cheat sheet in
  `docs/14-testing.md` covers every previous invocation; the
  `make help` output groups the new recipe under "Tests" with the
  variable list inline in its `##` annotation.
