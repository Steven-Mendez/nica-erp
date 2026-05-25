# Contributing to nica-erp

How to file bugs, propose changes, and ship PRs against the nica-erp monorepo. Applies equally to humans and AI-assisted contributors — both follow the same conventions so diffs are reviewable and the codebase stays coherent.

**Scope of this document.** Contribution **process** — bug reports, change proposals, branches, commits, PRs, code review, AI policy. Everything else (architecture, testing strategy, logging, API rules, naming, deployment) has a single source of truth under [`docs/`](./docs/README.md); this file links to those rather than duplicating them.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [First-time setup](#2-first-time-setup)
3. [Reporting bugs](#3-reporting-bugs)
4. [Suggesting enhancements](#4-suggesting-enhancements)
5. [Development process](#5-development-process)
6. [Pre-PR checklist](#6-pre-pr-checklist)
7. [AI-assisted contributions](#7-ai-assisted-contributions)
8. [Pre-deploy checklist](#8-pre-deploy-checklist)
9. [Questions](#9-questions)

---

## 1. Prerequisites

### Reading list (before your first non-trivial PR)

- [README.md](./README.md) — stack and quick-start
- [`docs/01-overview.md`](./docs/01-overview.md) — what we're building and why
- [`docs/02-architecture.md`](./docs/02-architecture.md) — hexagonal + DDD layering rules (non-negotiable)
- [`docs/14-testing.md`](./docs/14-testing.md) — test levels, fixtures, markers
- [`docs/15-local-development.md`](./docs/15-local-development.md) — local dev loop
- [`docs/16-tooling.md`](./docs/16-tooling.md) — toolchain, style, naming, code conventions

ADRs (architectural decisions) live in [`docs/adr/`](./docs/adr/README.md). Read the relevant ADR before changing something it covers.

### Host tools

All four must be on `PATH` before `make install`. Verify with `make doctor`.

| Tool | Install (macOS) | Install (any) |
| --- | --- | --- |
| **`uv`** | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node `>=22 <25`** (`.nvmrc` = active LTS) | `brew install node` | `nvm install` |
| **`pnpm@9`** (Homebrew Node does **not** ship corepack) | `brew install pnpm` | `npm i -g pnpm@9` |
| **Docker** | `brew install --cask docker` | Docker Desktop |

`pre-commit` is **not** a host prerequisite — it's an `apps/api` dev-dep installed by `uv sync`. Use `make hooks` to wire the git hook.

For infra work (sprint 01+): Terraform `>=1.7` and AWS credentials.

---

## 2. First-time setup

```bash
make doctor          # verify uv, node, pnpm, docker are on PATH
make install         # uv sync + pnpm install
make hooks           # install the pre-commit git hook (once per clone)
```

Why `make hooks` and not `uv run pre-commit install`? `pre-commit` is an `apps/api` dev-dep, so it can only be invoked with `apps/api`'s `uv` env active. `make hooks` does the `cd` for you.

### Daily commands

| Task                       | Command                                                |
| -------------------------- | ------------------------------------------------------ |
| Start local infra          | `make local-up` (Postgres + LocalStack + Mailpit)      |
| Stop local infra           | `make local-down`                                      |
| Run API (`:8000`)          | `make api`                                             |
| Run web (`:5173`)          | `make web`                                             |
| Apply migrations           | `make migrate`                                         |
| Rollback last migration    | `make migrate-down`                                    |
| Create empty migration     | `make makemigration M="<message>"`                     |
| Create autogen migration   | `make makemigration-auto M="<message>"`                |
| Run tests                  | `make test` (defaults to unit)                         |
| Lint (API + web)           | `make lint`                                            |
| Format (API + web)         | `make format`                                          |
| Regenerate web API client  | `cd apps/web && pnpm gen:api` (API must be running)    |

Local dev loop in detail: [`docs/15-local-development.md`](./docs/15-local-development.md).

---

## 3. Reporting bugs

### Before submitting

1. Search existing [GitHub issues](../../issues) (open and closed).
2. Verify on `main` — not just your local branch.
3. If the bug touches infra, confirm it reproduces in a clean `make local-up` environment.

### Where to file

[GitHub Issues](../../issues/new) with the `bug` label.

### What to include

- **Steps to reproduce:** exact commands or UI actions.
- **Expected vs actual behavior:** what should happen vs what does.
- **Environment:** Local / Docker / ephemeral AWS / staging. Include `APP_ENV` and any non-default env vars.
- **Correlation ID:** from the response header `X-Correlation-ID` or the log line.
- **Logs / stack trace:** trimmed to the relevant lines.
- **Affected context:** which bounded context (e.g. `sales`, `inventory`, `iam`) — see [`docs/03-bounded-contexts.md`](./docs/03-bounded-contexts.md).

---

## 4. Suggesting enhancements

nica-erp uses the **OpenSpec workflow** for non-trivial changes. Drive-by tweaks (typos, formatting, single-line bug fixes) can skip it.

### Workflow

1. Discuss the idea in a [GitHub Discussion](../../discussions) first.
2. Use `opsx:explore` (or `/openspec-explore`) to think through the problem.
3. Use `opsx:propose` (or `/openspec-propose`) to generate the proposal artifacts in `openspec/`.
4. Open a PR with the proposal. Once approved, implement with `opsx:apply` and archive with `opsx:archive` when done.

See [`openspec/config.yaml`](./openspec/config.yaml) and the command definitions under [`.claude/commands/opsx/`](./.claude/commands/opsx/).

### What a good proposal includes

- **Problem statement:** what problem does this solve? Which user / tenant feels the pain?
- **Proposed solution:** how it should work, end-to-end.
- **Alternatives considered:** what else was on the table and why it lost.
- **Impact:** bounded contexts touched, migrations needed, ADRs affected.
- **Non-goals:** what you are explicitly **not** doing in this change.

---

## 5. Development process

### Types of changes

| Type          | Use for            | Branch      | Commit          |
| ------------- | ------------------ | ----------- | --------------- |
| Feature       | New capability     | `feat/`     | `feat:`         |
| Bug fix       | Fixing bugs        | `fix/`      | `fix:`          |
| Refactor      | No behavior change | `refactor/` | `refactor:`     |
| Documentation | Docs / ADRs        | `docs/`     | `docs:`         |
| Test          | Test additions     | `test/`     | `test:`         |
| Chore         | Tooling, deps      | `chore/`    | `chore:`        |
| Performance   | Optimizations      | `perf/`     | `perf:`         |
| Infra         | Terraform / CI     | `infra/`    | `chore(infra):` |

### Branch naming

Format: `<type>/<short-description>`. Examples:

```
feat/tenant-rls-policies
fix/outbox-publisher-retry
refactor/issue-invoice-use-case
docs/adr-0030-fx-source
infra/cloudfront-spa-routing
```

Reference the related OpenSpec change or GitHub issue in the PR description, not the branch name.

### Commit messages

Format: `<type>(<scope>): <description>` — Conventional Commits.

- **Scope** is optional but recommended. Use the bounded context or module (`sales`, `inventory`, `iam`, `outbox`, `web`, `api`, `infra`).
- **Description** is lowercase, imperative mood, no trailing period. Proper nouns and filenames stay cased.

Good:

```
feat(sales): issue invoice allocates DGI number sequence
fix(outbox): retry with exponential backoff on EventBridge 5xx
refactor(iam): extract TenantScope into shared_kernel
docs(adr): add 0030 BCN FX rate source
chore(deps): bump fastapi to 0.115.4
```

Bad: `WIP`, `fixed stuff`, `update code`, `feat: Added new feature.` (capitalized, past tense, period).

### Pull requests

**Title:** human-readable summary; for single-commit PRs use the same shape as the commit message.

**Body should include:**

- **Summary:** 1–3 bullets on what changed and why.
- **Related:** OpenSpec change folder, GitHub issue, ADR.
- **Test plan:** how you verified it, including the commands you ran.
- **Screenshots:** for any UI change.
- **Migration / rollback notes:** if the PR adds an Alembic migration or changes RLS policies.

**Code review:**

1. CI must be green (`api-checks.yml`, `web-checks.yml`).
2. At least one approval from a maintainer.
3. Resolve every review comment (reply or push a fix); do not click "Resolve" on someone else's comment without addressing it.

### Git practices

- Branch from `main`. Rebase onto `main` before requesting review if `main` has moved significantly.
- Small, focused commits. One logical change per commit.
- Never commit directly to `main`. Never commit `.env`, `*.tfstate`, `*.pem`, AWS credentials, or anything under `apps/api/.venv/`.
- PRs target `main` — staging is a deployment target, not a branch ([ADR-0003](./docs/adr/0003-deploy-destroy-per-env.md)).
- Prefer **squash merge** for small PRs; **merge commit** for multi-commit feature work where individual commits tell a story.
- Force-push only your own un-merged branches.
- Never `--no-verify` on a commit. If a hook fails, fix the underlying issue ([ADR-0023](./docs/adr/0023-no-ci-cd-mvp.md) says CI is local-equivalent — bypassing locally just defers the failure to CI).

### Breaking changes

"Breaking" means: public API contract change (request/response shape, error code, status code); domain event payload change (consumers may break); schema change that requires a backfill or coordinated deploy; ADR supersession.

Process: open a Discussion → write or update the ADR → land the change behind a version bump (`/v1` → `/v2` for HTTP; new event name for events) per [ADR-0027](./docs/adr/0027-api-versioning.md).

---

## 6. Pre-PR checklist

Run locally before requesting review. CI runs the same checks.

```bash
make lint && make test && cd apps/web && pnpm test:run
```

What that covers — and where the rules live:

| Check                                          | Where the rule is canon                                                                |
| ---------------------------------------------- | --------------------------------------------------------------------------------------- |
| Hexagonal layering (`import-linter`)           | [`docs/02-architecture.md`](./docs/02-architecture.md)                                  |
| Python style, naming, comments, file paths     | [`docs/16-tooling.md` §Code conventions](./docs/16-tooling.md#code-conventions)         |
| TypeScript style, OpenAPI client, forms, state | [`docs/09-frontend.md`](./docs/09-frontend.md) + [`docs/16-tooling.md`](./docs/16-tooling.md) |
| Test level + location (`tests/{unit,integration,contract,e2e}/` mirroring `src/`, files named `test_*.py`) | [`docs/14-testing.md`](./docs/14-testing.md) |
| Logging conventions (structured, no PII)       | [`docs/12-observability.md` §Writing logs](./docs/12-observability.md#writing-logs-for-contributors) |
| Security do/don't (no PII logs, no `eval`, …)  | [`docs/06-security-model.md` §Contributor checklist](./docs/06-security-model.md#contributor-security-checklist) |
| API contract changes (versioning, error codes) | [`docs/08-api-conventions.md`](./docs/08-api-conventions.md)                            |

If you added an endpoint, follow [`docs/08-api-conventions.md` §Adding or changing an endpoint](./docs/08-api-conventions.md#adding-or-changing-an-endpoint-contributor-workflow) — including `pnpm gen:api` to regenerate the typed client.

---

## 7. AI-assisted contributions

You may use Claude Code, Copilot, Cursor, or any other AI assistant. The same rules apply: **the human submitting the PR is responsible for the diff.** Reviewers should not need to know whether a line was typed by a human or generated by a model.

### Expectations

- **The full PR has been read and understood by the submitter.** Don't paste a generated diff you haven't read.
- **The diff respects the layering** (`domain ← application ← adapters`). `import-linter` catches the obvious ones; you catch the subtle ones (a "shared util" placed in `domain/` that uses SQLAlchemy).
- **Comments follow [§Comments in `docs/16-tooling.md`](./docs/16-tooling.md#comments).** No `# Increment the counter`. No multi-paragraph docstrings restating the signature. No "added for the new flow" references that rot.
- **Project naming.** Distribution package: `nica-erp`. Python source lives under `apps/api/src/` with top-level packages `bootstrap`, `shared_kernel`, `contexts` — no wrapping namespace. Imports are `from bootstrap.X`, `from shared_kernel.X`, `from contexts.X` (never `from nica_erp.X`).
- **Tests are real.** AI tools occasionally write tautologies — tests that assert what the implementation does rather than what the spec requires. Read the test and ask: would this fail if the implementation were wrong?
- **No invented APIs or fields.** Verify every function call, import, and field reference points at something that actually exists.
- **No bulk reformatting.** If you ran an AI tool that reformatted unrelated files, reset them before committing.

### Guardrails the project enforces

- `ruff`, `mypy --strict` (on `domain/` + `application/` + `bootstrap/`), `import-linter`, and `pre-commit` reject most layering and style violations.
- `tsc --noEmit` + ESLint catch the same on the frontend.
- CI (`api-checks.yml`, `web-checks.yml`) re-runs the same checks. A PR that's green locally should be green in CI.

### OpenSpec + AI

For non-trivial changes, use the OpenSpec commands (`opsx:explore`, `opsx:propose`, `opsx:apply`, `opsx:archive`). A proposal generates `proposal.md`, `design.md`, and `tasks.md` under `openspec/changes/<id>/`, the implementation works off those tasks, and the change archives into `openspec/archive/`. Review the proposal **before** approving implementation — that's where the model's judgment matters most.

### When to push back on the AI

- Suggests a "compatibility shim" or "fallback" for code that doesn't exist yet → delete it.
- Writes a multi-paragraph docstring for a one-line function → delete the docstring.
- Adds `try/except` around code that can't fail → delete the handler.
- Generates a test that mocks the database → rewrite as an integration test with `testcontainers`.
- Invents a Make target, env var, or ADR number → check `Makefile`, `.env.local.example`, or `docs/adr/` first.

---

## 8. Pre-deploy checklist

Deploys are manual ([ADR-0023](./docs/adr/0023-no-ci-cd-mvp.md)). Detail in [`docs/11-deployment.md`](./docs/11-deployment.md). Before running `make deploy`:

- [ ] `make lint` clean (API + web).
- [ ] `make test` green (unit at minimum; run integration if you touched an adapter).
- [ ] Frontend client regenerated if the API contract changed (`pnpm gen:api`).
- [ ] Alembic migration tested locally with `make migrate` **and** `make migrate-down` (round-trip).
- [ ] No breaking API change without a `/v2` plan and `Sunset` headers ([ADR-0027](./docs/adr/0027-api-versioning.md)).
- [ ] Sensitive env vars in SSM, not in `.env` ([ADR-0021](./docs/adr/0021-ssm-parameter-store.md)).
- [ ] If the deploy touches a new bounded context: relevant ADR exists and is linked in the PR.

---

## 9. Questions

- General discussion → [GitHub Discussions](../../discussions)
- Bugs → [GitHub Issues](../../issues)
- Security → private GitHub Security Advisory (do **not** open a public issue for security)
- Architectural questions → open an ADR draft PR in [`docs/adr/`](./docs/adr/)
