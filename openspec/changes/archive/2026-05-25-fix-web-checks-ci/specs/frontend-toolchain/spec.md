## MODIFIED Requirements

### Requirement: Continuous integration runs the web checks on every push

`.github/workflows/web-checks.yml` MUST run on `push` to `main` and on every `pull_request` whose changes touch `apps/web/**` or the workflow file itself. The job MUST execute under `apps/web/` working directory and consist of the following steps in order: checkout, install pnpm (version 9), install Node from `.nvmrc` with pnpm cache keyed on `apps/web/pnpm-lock.yaml`, run `pnpm install --frozen-lockfile`, then run `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, and `pnpm test:run`. The workflow MUST NOT deploy anything (per [ADR-0023](../../../../docs/adr/0023-no-ci-cd-mvp.md)).

The third-party actions used by both `web-checks.yml` and `api-checks.yml` MUST be pinned to the current latest major as published by each action's maintainer (verifiable via Context7 / each action's README): `actions/checkout@v6`, `actions/setup-node@v6`, `pnpm/action-setup@v6`, and `astral-sh/setup-uv@v8`. Pinning to a major that GitHub has marked deprecated (currently anything running on Node.js 20) is forbidden.

#### Scenario: PR touching the web app triggers the workflow

- **WHEN** a pull request modifies a file under `apps/web/`
- **THEN** GitHub Actions runs `web-checks` and the job fails if any of typecheck, lint, format:check, or test:run exits non-zero

#### Scenario: Lockfile is honoured

- **WHEN** the CI job installs dependencies
- **THEN** it runs `pnpm install --frozen-lockfile` so an out-of-date `pnpm-lock.yaml` fails the build rather than silently regenerating

#### Scenario: No deprecated action versions

- **WHEN** the workflow runs on a GitHub-hosted runner
- **THEN** the run logs do NOT contain the "Node.js 20 actions are deprecated" warning, because every `uses:` line resolves to a major running on node24

## ADDED Requirements

### Requirement: `.gitignore` MUST NOT swallow `apps/web/src/lib/`

The root `.gitignore` is seeded from the [GitHub Python template](https://github.com/github/gitignore/blob/main/Python.gitignore) and contains a generic `lib/` rule for setuptools build artefacts. That rule MUST be neutralised for `apps/web/src/lib/` (the shadcn helpers directory referenced by `components.json` aliases `@/lib/utils`). The neutralisation MUST take the form of an explicit negation pair (directory then contents) placed below the original Python rules, with a comment that records the reason. Other `lib/` paths (Python build outputs in `apps/api/` or future services) MUST continue to be ignored.

#### Scenario: shadcn helper is tracked

- **WHEN** a fresh clone of the repo is checked out
- **THEN** `apps/web/src/lib/utils.ts` is present on disk and tracked by git (`git ls-files apps/web/src/lib/utils.ts` is non-empty)

#### Scenario: Python build artefacts stay ignored

- **WHEN** a developer accidentally creates `apps/api/build/lib/` (setuptools output)
- **THEN** `git status` does NOT list the directory because the original `lib/` rule still matches non-frontend paths
