## MODIFIED Requirements

### Requirement: Triad-respecting test lanes

The Makefile SHALL expose a single parametrized recipe so
contributors can run the cheapest layer first without paying
the cost of the slower layers. The recipe SHALL accept a
`SCOPE` variable (`be` to restrict to the backend) and a
`LANE` variable (`unit`, `integration`, or `e2e`) and SHALL
translate `LANE=<lane>` into a pytest invocation that targets
only the matching directory under `apps/api/tests/`.

#### Scenario: Unit lane runs only `tests/unit/`

- **WHEN** a contributor runs `make test SCOPE=be LANE=unit`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/unit`
- **AND** the run SHALL NOT spin up the Postgres testcontainer
- **AND** the run SHALL complete in under ten seconds on a warm
  cache

#### Scenario: Integration lane runs only `tests/integration/`

- **WHEN** a contributor runs `make test SCOPE=be LANE=integration`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/integration`
- **AND** the Postgres testcontainer SHALL boot exactly once for
  the session

#### Scenario: E2E lane runs only `tests/e2e/`

- **WHEN** a contributor runs `make test SCOPE=be LANE=e2e`
- **THEN** the recipe SHALL run `cd apps/api && uv run pytest
  tests/e2e`
