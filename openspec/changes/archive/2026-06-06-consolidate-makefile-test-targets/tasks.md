## 1. Rewrite `make/test.mk`

- [ ] 1.1 Replace the eleven discrete test recipes with a single
      `test` recipe that branches on `SCOPE`, `LANE`, and `COV`
      shell variables. Keep `test-e2e-smoke` (renamed from
      `test-fe-e2e`) as the Playwright entry point.
- [ ] 1.2 The recipe's `##` annotation in the help banner SHALL
      list every supported variable inline:
      `SCOPE=be|fe LANE=unit|integration|e2e COV=1` and a one-line
      description.
- [ ] 1.3 The bare `make test` invocation (no variables) SHALL run
      the full backend triad (unit + integration + e2e) and the
      full frontend vitest run, with no coverage gates and no
      Playwright.
- [ ] 1.4 `make test COV=1` SHALL run the backend coverage gate
      against `src/contexts/tenants`, `src/contexts/identity`,
      `src/shared_kernel` with `--cov-fail-under=89` (no change
      from the current `test-be-coverage` recipe) and the
      frontend `pnpm exec vitest run --coverage` AND
      `pnpm test:layout && pnpm test:matrix`.
- [ ] 1.5 `make test SCOPE=be LANE=unit` SHALL run only
      `cd apps/api && uv run pytest tests/unit` and SHALL NOT
      start the Postgres testcontainer.
- [ ] 1.6 `make test SCOPE=fe LANE=integration` SHALL run only
      `cd apps/web && pnpm test:integration`.
- [ ] 1.7 Update `.PHONY` and remove the eleven dead target names.

## 2. Update `backend-test-quality-guards` spec

- [ ] 2.1 Modify the "Triad-respecting test lanes" requirement and
      its three scenarios to refer to
      `make test SCOPE=be LANE=<lane>` instead of the discrete
      `test-be-<lane>` recipes.
- [ ] 2.2 Update the Purpose paragraph's parenthetical (currently
      "Three Makefile lanes (`test-be-unit`, …)") to the new
      invocation form. The rest of the Purpose paragraph (defect-
      finding power, property tests, etc.) is unchanged.
- [ ] 2.3 No other requirements in this spec mention Makefile
      targets — verify by `grep -n 'make ' openspec/specs/backend-test-quality-guards/spec.md` after the edit.

## 3. Update `test-coverage` spec

- [ ] 3.1 Modify the "Backend coverage gate" requirement so its
      scenario refers to `make test SCOPE=be COV=1`. The
      90%-of-the-listed-trees threshold is unchanged.
- [ ] 3.2 Modify the "Frontend coverage gate" requirement so its
      scenario refers to `make test SCOPE=fe COV=1`. The 80%
      threshold on `features/` + `components/` is unchanged.
- [ ] 3.3 Modify the "Sprint-03 RLS isolation gate" requirement so
      it refers to "the default `make test` invocation" instead of
      the never-existed `make test-e2e`.
- [ ] 3.4 Modify the "Coverage thresholds are tree-scoped"
      requirement's scenario so it refers to `make test SCOPE=be
      COV=1`. The behavior (bootstrap tree outside scope) is
      unchanged.

## 4. Update documentation

- [ ] 4.1 In `docs/14-testing.md`, add a "Test invocation cheat
      sheet" subsection with the old→new mapping table from
      `design.md`.
- [ ] 4.2 Replace every `make test-be-<x>`, `make test-fe-<x>`,
      `make test-all`, `make test-fe-all` reference in
      `docs/14-testing.md` with the new parametrized form.
- [ ] 4.3 Update `CONTRIBUTING.md` line 75 (the "Run tests" row
      of the cheat-sheet table) and any other references to the
      removed recipes.
- [ ] 4.4 Update `docs/sprints/03-tenants-and-rls.md` references
      ONLY in current/forward-looking sections (the historical
      narrative SHALL be left untouched — sprint docs are
      append-only). Confirm by reading the file before editing.
- [ ] 4.5 Final sweep: `grep -rnE "make test-(be|fe|all)" docs/
      CONTRIBUTING.md README.md` SHALL return only intentional
      historical references (e.g., archived sprint sections).

## 5. Verification

- [ ] 5.1 Run `make help` and confirm the Tests section shows
      only `test` (with the variable list) and `test-e2e-smoke`.
- [ ] 5.2 Run `make test SCOPE=be LANE=unit` and confirm it
      completes in under ten seconds on a warm cache (the unit
      lane's existing contract).
- [ ] 5.3 Run `make test SCOPE=be COV=1` and confirm the coverage
      report shows the three trees and the failure threshold is
      89%.
- [ ] 5.4 Run `make test SCOPE=fe COV=1` and confirm vitest reports
      coverage AND the inventory matrix check runs.
- [ ] 5.5 Run `make test` and confirm both stacks run all lanes
      with no coverage gates.
- [ ] 5.6 Run `make test-e2e-smoke` and confirm Playwright @smoke
      starts (skip if Chromium not installed; the rename is the
      only contract this scenario covers).
