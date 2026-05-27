# ADR-0030 — Deploy/destroy run in GitHub Actions; bootstrap stays on the operator's host

**Status**: Accepted (supersedes [ADR-0023](0023-no-ci-cd-mvp.md))
**Date**: 2026-05-26

## Context

[ADR-0023](0023-no-ci-cd-mvp.md) decided "GitHub Actions for static verification only; all deploys are manual `make` from the operator's machine." That decision rested on two assumptions that have both broken:

1. **The operator's machine can run every operation.** The operator's host is Apple Silicon (arm64); `docker build --platform linux/amd64` under QEMU emulation segfaults during `uv sync` while building the API image. The deploy path cannot run locally.
2. **CI/CD costs more than it pays.** ADR-0023 cited "long-lived AWS credentials stored as repo secrets" as the cost. With OIDC federation that cost disappears — workflows assume short-lived roles via the GitHub OIDC issuer, no static keys anywhere.

The right move is the path ADR-0023 itself anticipated: OIDC-federated GitHub Actions, no long-lived secrets — with a deliberate brake on the trigger (`workflow_dispatch` only, no `push:` triggers). But not every operation moves: bootstrap (the persistent infrastructure that includes the IAM/OIDC plumbing itself) is unavoidably an operator-only local-host operation, and pretending otherwise creates a chicken-and-egg problem with no clean resolution.

## Decision

**The deploy/destroy cycle runs in GitHub Actions via `workflow_dispatch`. The bootstrap/destroy-bootstrap cycle runs from the operator's host with the `nica-erp` AWS CLI profile. Both halves are explicit; neither has automatic triggers.**

### Four operations, two surfaces

| Make target | Surface | Why this surface |
|---|---|---|
| `make bootstrap` | **operator's host, operator-only** | creates the GitHub OIDC provider and the CI IAM roles. A workflow cannot create the role it would need to authenticate (chicken-and-egg). The `nica-erp` AWS CLI profile is the only path that exists before bootstrap has run. |
| `make destroy-bootstrap` | **operator's host, operator-only** | the persistent infra holds irrecoverable state (S3 versions, CloudFront domain). The existing terminal-prompt confirmation (`Type 'nica-erp-bootstrap' to confirm`) in the script is the safety; a workflow input adds nothing and removes the typed prompt. Admin-only by design. |
| `make deploy` | **GHA workflow** (`deploy.yml`, `workflow_dispatch`) | end-to-end deploy: builds the API image, applies the ephemeral Terraform stack, runs migrations, registers the new ECS task definition, builds and uploads the SPA, invalidates CloudFront. This is the operation the operator's host cannot do because of the QEMU segfault. |
| `make destroy` | **GHA workflow** (`destroy.yml`, `workflow_dispatch` + `confirm` input) | tears down the ephemeral stack only. Bootstrap survives so the next deploy is ~10 min, not ~30 min ([ADR-0003](0003-deploy-destroy-per-env.md)). |

### What `make deploy` actually does, in one workflow

`deploy.yml` runs sequentially on `ubuntu-latest`:

1. Checkout (full history, so the build's `git rev-parse HEAD` matches the operator-host view).
2. Assume `nica-erp-ci-deploy` via OIDC.
3. `docker build --platform linux/amd64 --build-arg GIT_SHA=$(git rev-parse HEAD)` and `docker push` to ECR. Tag = `git rev-parse --short HEAD`.
4. `terraform apply` on the ephemeral root (`infra/terraform/envs/demo/`). Reads bootstrap outputs from the state backend.
5. ECS RunTask: `alembic upgrade head` against the freshly-applied RDS.
6. Register the new ECS task definition with the pushed image tag; ECS rolls the service.
7. Wait for the ALB target group to report `healthy` for the new tasks.
8. `pnpm build` for the SPA with `VITE_API_BASE_URL=/api`. `aws s3 sync` to the SPA bucket.
9. `cloudfront create-invalidation --paths '/*'`.
10. Step summary: pushed image tag, alembic revision applied, CloudFront URL, ECS task definition ARN.

Single workflow file, single dispatch, single rollback unit. If any step fails, the prior task definition stays active (ECS rolling deploy semantics from [ADR-0018](0018-rolling-deploys.md)).

### Auth: OIDC, one provider, two roles

The bootstrap Terraform creates:

1. One `aws_iam_openid_connect_provider` for `token.actions.githubusercontent.com` (AWS hard-limit: one per `url` per account).
2. `nica-erp-ci-deploy` — assumed by `deploy.yml`. Inline policy grants:
   - ECR push on the `nica-erp` repo ARN (image step);
   - state-backend read/write on `nica-erp-tf-state-*` and `nica-erp-tf-lock` (Terraform);
   - apply-side actions for the ephemeral resources (VPC, RDS, ECS, ALB, Cognito, SSM, observability);
   - S3 PutObject on the SPA bucket + `cloudfront:CreateInvalidation` on the bootstrap distribution.
3. `nica-erp-ci-destroy` — assumed by `destroy.yml`. Inline policy grants:
   - the destroy-side actions on the same ephemeral resource surface;
   - state-backend read/write.
   - **NOT** granted: `s3:DeleteBucket` on the state/SPA buckets, `ecr:DeleteRepository`, `cloudfront:DeleteDistribution`, `iam:DeleteOpenIDConnectProvider`, `iam:DeleteRole`. The destroy workflow cannot touch the bootstrap surface.

Both roles' trust policies bind to `repo:Steven-Mendez/nica-erp:ref:refs/heads/main` only. Feature-branch workflows cannot assume them.

Each role's ARN is exposed as a Terraform output (`ci_deploy_role_arn`, `ci_destroy_role_arn`); `scripts/bootstrap.sh` prints both at the end alongside the two literal `gh variable set` lines the operator pastes once.

### Confirmation gate on `make destroy`

`destroy.yml` requires a required input `confirm` of `type: string` with no default. The workflow's first step asserts the value equals `nica-erp-ephemeral` and exits non-zero before any AWS call on mismatch. `make destroy` pre-fills the value; an operator dispatching from the Actions tab must type it.

`make destroy-bootstrap` does not need this gate because it runs from the operator's host with the existing terminal-prompt confirmation.

### Auto-trigger on push to `main` is intentionally not enabled

`deploy.yml`'s `on:` block is structured so adding `push: branches: [main]` is a single line. The `nica-erp-ci-deploy` role already trusts that ref. The day the team grows past one developer, the brake comes off with a YAML one-liner — no AWS-side change.

## Consequences

- **(+)** The operator does not need x86 hardware for the recurring deploy/destroy cycle. Apple Silicon + `gh` + a browser is enough.
- **(+)** No static AWS credentials anywhere. Short-lived OIDC tokens for CI; the `nica-erp` profile on the operator's host for the two bootstrap operations.
- **(+)** `make deploy` is one command, one workflow run, one rollback unit. The operator does not orchestrate "build image then deploy" by hand.
- **(+)** The destroy role cannot touch the bootstrap surface — a leaked role assumption cannot delete the state bucket or the OIDC provider.
- **(+)** Auto-trigger on push to `main` is a one-line YAML diff away.
- **(−)** Two surfaces to learn (operator's host for project-lifecycle ops, GHA for the deploy cycle). Documented in [Sprint 01](../sprints/01-aws-wiring-rolling-deploys.md) §Operations.
- **(−)** First-time setup has a manual hand-off: after `make bootstrap`, the operator pastes the two `gh variable set` lines the script prints. Documented in the script's own output.
- **(−)** Bootstrap operations remain a single point of failure (operator unavailable = no first-time setup, no project close). Acceptable for one-developer MVP; revisit when a second operator is on board.

## Alternatives considered

- **Status quo (ADR-0023, operator-host-only)**: rejected — Apple Silicon cannot build the production image.
- **Five workflows (one per `make` target)**: rejected — bootstrap's chicken-and-egg cannot be cleanly automated, and `make build-image` standalone is unnecessary once `make deploy` builds the image as its first step.
- **Static AWS keys in GitHub Secrets**: rejected — ADR-0023 already pre-committed to OIDC. Not significantly harder to set up.
- **One fat workflow with `op:` input dispatching to deploy/destroy**: rejected — would force the deploy IAM permissions on every destroy and vice versa, blurring audit trails.
- **CodeBuild or self-hosted runners**: rejected — adds a second compute surface for one developer. GitHub-hosted runners cover this volume well inside the free tier.

## Revisit triggers

Re-open this decision when any of the following becomes true:

1. **Second contributor lands** — enable `push: branches: [main]` on `deploy.yml` so every merge produces an image and updates the stack. The IAM role already trusts that ref.
2. **First productive tenant** — manual dispatch becomes a single point of failure. Gate auto-trigger on a `staging` GitHub environment with manual review.
3. **Second AWS operator joins** — revisit whether bootstrap should also move into a workflow (with environment-gated approval) so the project does not depend on one operator's host being available.
4. **Cross-account or cross-region** — the trust policy and the role inline policies need re-scoping.

## References

- [Sprint 01](../sprints/01-aws-wiring-rolling-deploys.md) §Operations — sprint-narrative view.
- [ADR-0023](0023-no-ci-cd-mvp.md) — the predecessor decision this supersedes.
- [ADR-0003](0003-deploy-destroy-per-env.md) — the "ephemeral stack on demand" model the destroy workflow preserves.
- [ADR-0018](0018-rolling-deploys.md) — the rolling-deploys DoD that this ADR makes accessible from an Apple Silicon operator host.
