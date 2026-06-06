## Context

The Makefile-as-operator-UX has a target sprawl problem. Twelve
test recipes for two test suites is more verbs than the operator
keeps in their head; the spec files inherit that sprawl by naming
five of the recipes verbatim. The previous Makefile cleanup pass
(this conversation, prior step) collapsed the rest of the surface
by ~12% but stopped short of touching the test triad because the
contracts referenced the names.

Two structural facts shape this change:

1. **CI does not use `make` for tests.** `api-checks.yml` and
   `web-checks.yml` invoke `uv run pytest -m unit` and
   `pnpm test:unit` directly. So the Makefile target names are
   *operator UX*, not a *contract with CI*. We are free to
   reshape them as long as the spec and docs follow.
2. **Two suites with different filtering models.** The backend
   suite uses directory-based lanes (`tests/unit/`,
   `tests/integration/`, `tests/e2e/`). The frontend uses vitest
   project filtering (`pnpm test:unit`, `pnpm test:integration`),
   plus a wholly separate Playwright runner (`pnpm test:e2e:smoke`).
   A single parametrized recipe has to respect both shapes.

## Goals / Non-Goals

**Goals:**

- One recipe, `make test`, that the operator can invoke with zero
  variables for "run everything" and a single variable for the
  three real workflows ("only one stack", "only one lane",
  "with the coverage gate").
- Spec wording that survives the next reshuffle: the contract
  describes *what runs*, the variable list lives in `make help`.
- Playwright stays a separate recipe so it is discoverable and
  does not surprise contributors who don't have browsers
  installed.

**Non-Goals:**

- A single `make test` that also runs Playwright. Browsers and
  the `@smoke` marker make this meaningfully different.
- A `LANE=matrix` for the FE inventory check. The matrix is
  morally a coverage gate (it asserts every inventory entry has
  a covering test), so it rides with `COV=1`.
- An `E2E=0` shortcut. `LANE=unit,integration` is one extra
  character to type and avoids a second knob with overlapping
  semantics.

## Decisions

### Decision 1: One recipe with three orthogonal variables

`make test` accepts `SCOPE`, `LANE`, and `COV`. Each defaults to
"the broadest sensible value" so the bare `make test` runs
everything except Playwright.

Alternative considered: keep `test-be` / `test-fe` as separate
recipes and only collapse the lane variants. Rejected because
the SCOPE knob is the cheapest part of the implementation (a
single `if [ "$(SCOPE)" != "fe" ]` shell guard) and a separate
recipe would mean two help entries doing the same work.

Alternative considered: replace `COV=1` with a separate
`make test-coverage` recipe. Rejected because the coverage gate
is the canonical CI parity invocation; the operator who wants to
reproduce CI locally is the same operator who wants to scope it
to one stack (`make test SCOPE=be COV=1`). Two recipes would
duplicate the SCOPE branching.

### Decision 2: `LANE` is backend-only as a directory selector; frontend uses script names

Backend: `LANE=unit` → `uv run pytest tests/unit`. Backend lanes
are directories under `apps/api/tests/`.

Frontend: `LANE=unit` → `pnpm test:unit`. Frontend lanes are
vitest projects, addressed by `package.json` script names.

The recipe does the translation. Documenting "`LANE=unit` on the
frontend maps to `pnpm test:unit`" once in `docs/14-testing.md`
is cheaper than inventing a parallel `FE_LANE` variable.

### Decision 3: Spec scenarios refer to invocation, not implementation

Current spec scenarios say `make test-be-unit` and `cd apps/api &&
uv run pytest tests/unit`. The new scenarios say
`make test SCOPE=be LANE=unit` and the same implementation line.
The implementation line is preserved verbatim because it captures
the speed / fixture-cost contract (no testcontainer for unit, one
testcontainer per session for integration). Only the operator-
facing invocation changes.

### Decision 4: Playwright recipe is renamed `test-e2e-smoke`, not `test-fe-e2e`

Previous name was `test-fe-e2e`, which suggested "frontend e2e
lane of the triad". That was misleading — Playwright is a wholly
different runner with different setup, browser deps, and
expectations. The new name surfaces the marker (`@smoke`) and
breaks the false symmetry with the vitest lanes.

This rename is not spec-locked: `test-fe-e2e` does not appear in
any active spec.

## Risks

- **Documentation drift.** Five recipe names are about to
  disappear from `docs/` and `CONTRIBUTING.md`. The change tasks
  include a sweep, but anything we miss will leave broken
  invocations. Mitigation: a `grep -rn 'make test-' docs/
  CONTRIBUTING.md README.md` clean-room check is the last task
  before archive.
- **Operator muscle memory.** Contributors who type
  `make test-be-coverage` 20 times a week will hit a
  "no rule to make target" error on first use. Mitigation: leave
  a one-cycle deprecation alias if the noise is worth the cost.
  *Decision:* no alias. The new form is one character longer
  (`make test SCOPE=be COV=1` vs. `make test-be-coverage`), the
  spec change is hard to discover without the error, and an
  alias would defeat the whole "reduce the help surface" point.
- **Spec drift on the Sprint-03 RLS gate.** The
  `test-coverage` spec references `make test-e2e`, which was
  never a real target — the spec was wrong before this change.
  Mitigation: this change corrects it to "the default `make test`
  invocation", and the same fix would have been needed regardless.

## Migration

A single cheat sheet section in `docs/14-testing.md`:

| Old                                | New                                  |
| ---                                | ---                                  |
| `make test`                        | `make test` (unchanged)              |
| `make test-be-unit`                | `make test SCOPE=be LANE=unit`       |
| `make test-be-integration`         | `make test SCOPE=be LANE=integration`|
| `make test-be-e2e`                 | `make test SCOPE=be LANE=e2e`        |
| `make test-be-coverage`            | `make test SCOPE=be COV=1`           |
| `make test-fe-unit`                | `make test SCOPE=fe LANE=unit`       |
| `make test-fe-integration`         | `make test SCOPE=fe LANE=integration`|
| `make test-fe-matrix`              | `make test SCOPE=fe COV=1` (folded into the FE coverage gate)|
| `make test-fe-coverage`            | `make test SCOPE=fe COV=1`           |
| `make test-fe-all`                 | `make test SCOPE=fe COV=1`           |
| `make test-all`                    | `make test COV=1`                    |
| `make test-fe-e2e`                 | `make test-e2e-smoke` (renamed)      |

The implementation is a single recipe with three shell guards;
the entire `make/test.mk` file ends up around 35 lines.
