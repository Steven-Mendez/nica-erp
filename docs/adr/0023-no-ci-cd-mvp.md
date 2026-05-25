# ADR-0023 — No automatic CI/CD for the MVP

**Status**: Accepted
**Date**: 2026-05-23

## Context
The stack runs on demand ([ADR-0003](0003-deploy-destroy-per-env.md)), there is no continuous productive traffic, and the team is one developer with one AWS account. Automatic deployment on merge would require long-lived AWS credentials stored as repo secrets and would deploy a stack that's intentionally idle most of the time.

## Decision
**GitHub Actions for static verification only. All deploys are manual via `make deploy` from the dev's machine with a local AWS profile.**

### Allowed workflows
| Workflow | Triggers | Runs |
|---|---|---|
| `api-checks.yml` | push, pull_request | `ruff check`, `ruff format --check`, `mypy --strict` over `domain/` + `application/`, `uv run lint-imports`, `pytest -m unit` |
| `web-checks.yml` | push, pull_request | `pnpm typecheck`, `pnpm lint --max-warnings=0`, `pnpm format:check`, `pnpm test --run` |

### Forbidden workflows
- Anything calling `terraform apply/destroy`.
- Anything calling `aws ecs ...`, `docker push` to ECR, or otherwise touching AWS resources.
- Any workflow using long-lived AWS credentials as a repo secret.

Pre-commit (`ruff`, `mypy`, `import-linter`, `pytest -m unit`, `pnpm typecheck`) is the first line; CI is the per-commit reproducible second line.

Detail in [`../11-deployment.md`](../11-deployment.md) and [`../16-tooling.md`](../16-tooling.md).

## Consequences
- (+) Zero AWS secrets in GitHub. No accidental deploys.
- (+) Per-commit reproducible static verification — branch protection requires checks green before merge.
- (+) Deploy is an explicit, observed action — easier to correlate failures with commits.
- (−) No automatic validation of the deploy flow itself. Mitigated by rolling deploys ([ADR-0018](0018-rolling-deploys.md)): every sprint exercises `make deploy` end-to-end.
- (−) With a second dev or first productive tenant, this becomes intentional tech debt. The path forward is a `staging` environment plus OIDC-federated GitHub Actions (no long-lived secrets) deploying on merge to `main`.

## Alternatives
- **GitHub Actions with deploy-on-merge** — rejected: needs AWS credentials in repo, adds little with one dev and no productive traffic.
- **No GitHub Actions at all (pre-commit only)** — rejected: loses per-commit reproducible verification.
- **CircleCI / Buildkite / GitLab CI** — rejected: extra account/billing surface for what GitHub Actions covers.

## Revisit triggers
Reopen this decision when any of the following becomes true:

1. **Second contributor lands** — branch protection alone is no longer enough; the team needs the deploy to be a reviewable action, not a private terminal command.
2. **First productive tenant** — manual deploy becomes a single point of failure (dev unavailable = no fix).
3. **More than one deploy per week sustained for a month** — manual cadence becomes friction.
4. **A `staging` environment is introduced** — promotion between envs needs to be a pipeline.

The follow-on ADR will spec OIDC federation (no static AWS keys in GitHub), a `staging` deploy on merge to `main`, and manual approval for `production`.
