# Sprint NN — Title

**Goal**: one sentence — the user-visible or operational outcome.

## Deliverables
- Concrete artifact (file, endpoint, table, infra resource)
- Each item must be testable

## Exit criteria
Every criterion is a command that returns exit 0 or a value that's evident.

- `pytest -m unit` exit 0, `domain/` + `application/` coverage ≥ 70%
- `pytest -m integration -k <area>` exit 0
- `pytest -m e2e -k <flow>` exit 0
- `ruff check`, `mypy --strict`, `pnpm typecheck`, `pnpm lint --max-warnings=0` all exit 0
- `make migrate && make migrate-down && make migrate` exit 0
- `make deploy` exit 0, post-deploy checklist passes (see [README §Post-deploy verification](README.md#post-deploy-verification)), `make destroy` exit 0

## Adapter swap (if applicable)
Which port is introduced this sprint and which adapter ships in AWS. Cross-reference [README §Adapters by environment](README.md#adapters-by-environment).

## Gate tests
Tests that must pass for this sprint to merge — beyond coverage. Examples: RLS isolation test, concurrent number-sequence test, N+1 gate.

## References
- ADRs: …
- Docs: …
