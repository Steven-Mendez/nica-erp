## Why

Changes 1–3 of sprint 01 give us state + image + a runnable AWS
stack, but they don't give us an **operator ergonomic** for running
the deploy/destroy loop that
[ADR-0018](../../../docs/adr/0018-rolling-deploys.md) makes part of
the DoD. Right now an operator would have to: read the right
Terraform variables, look up `terraform output -raw image_tag`, type
out `aws ecs run-task --launch-type FARGATE --network-configuration …`
to invoke the migration task, remember to invalidate CloudFront after
uploading the SPA, and trust that `terraform destroy` actually
removed everything. None of that is the kind of workflow you can do
nightly without losing patience.

This change is the **operator UX layer** that turns those steps into
`make deploy`, `make destroy`, `make deploy-web`, `make logs`, and
`make wipe`. It also closes two outstanding application-code seams
the runtime stack opened: the API has to know it is running in AWS
(so `CORSMiddleware` is **not** mounted, because CloudFront makes
everything same-origin) and the SPA has to build with
`VITE_API_BASE_URL=/api` so it talks to the API through the
CloudFront distribution rather than across origins.

After this change ships, the full DoD loop runs in three shell
commands from a clean account:
`make bootstrap && make deploy && make destroy`.

## What Changes

- **Application-code conditional CORS** in `apps/api/src/bootstrap/settings.py`:
  - When `app_env != "aws"` (default local/dev/test): existing
    behavior preserved — `CORS_ORIGINS` defaults to
    `["http://localhost:5173"]` and `bootstrap.api.create_app()`
    mounts `CORSMiddleware`.
  - When `app_env == "aws"`: `CORS_ORIGINS` defaults to `[]` and
    `bootstrap.api.create_app()` SKIPS mounting `CORSMiddleware`
    entirely. CloudFront makes the SPA and API share an origin, so
    CORS is a no-op in AWS. A unit test asserts each branch.
- **Frontend build env-var convention**:
  - `apps/web/.env.production` sets `VITE_API_BASE_URL=/api` (committed).
  - `apps/web/src/lib/api.ts` (or equivalent existing module) is
    audited to confirm `import.meta.env.VITE_API_BASE_URL` is used
    as the prefix for the healthz card's fetch call.
  - `apps/web/.env.local.example` documents the local override
    `VITE_API_BASE_URL=http://localhost:8000/api` (or whatever sprint
    00 already uses) for completeness.
- **New `scripts/run-migrations.sh`**:
  - Reads `cluster_name`, `migrate_task_definition_arn`,
    `task_subnets`, `task_security_group_id` from the demo env's
    Terraform outputs.
  - Calls `aws ecs run-task --launch-type FARGATE --cluster <c> --task-definition <td> --network-configuration "awsvpc..."`.
  - Polls the resulting task ARN with
    `aws ecs describe-tasks` until it transitions to `STOPPED`.
  - Exits with the container's exit code (so a failed migration
    fails the script and, transitively, fails `make deploy`).
- **New `scripts/deploy-web.sh`**:
  - Reads `cloudfront_distribution_id` and `web_bucket` from the
    bootstrap Terraform outputs.
  - Runs `VITE_API_BASE_URL=/api pnpm --filter @nica-erp/web build`.
  - Runs `aws s3 sync apps/web/dist/ s3://<web_bucket>/ --delete --cache-control "public, max-age=31536000, immutable"` for hashed assets,
    overriding `index.html` with
    `--cache-control "public, max-age=0, must-revalidate"`.
  - Issues `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`
    and waits for the invalidation to complete (`aws cloudfront wait invalidation-completed`).
- **New `scripts/deploy.sh`** orchestrating the full deploy:
  1. Read `.deploy-image-tag` (fail if missing).
  2. `terraform -chdir=infra/terraform/envs/demo init -input=false`.
  3. `terraform -chdir=infra/terraform/envs/demo apply -auto-approve -var "image_tag=$(cat .deploy-image-tag)"`.
  4. Run `scripts/run-migrations.sh`.
  5. Force a new ECS service deployment so the API picks up the
     new image even if its task-definition revision is unchanged
     (`aws ecs update-service --force-new-deployment`).
  6. Run `scripts/deploy-web.sh`.
  7. Poll `/api/healthz` with exponential backoff (max ~5 min) until
     it returns HTTP 200 and `db:"ok"`.
- **New `scripts/destroy.sh`**:
  1. `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`.
  2. Empty `nica-erp-web` (the SPA bucket is bootstrap-owned but
     gets re-populated each deploy; leaving stale assets between
     destroy cycles is acceptable, but the script offers
     `DESTROY_WEB_ASSETS=1` to empty it on demand).
- **New `scripts/verify-destroyed.sh`**:
  - Queries `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`.
  - Maintains an allow-list of bootstrap ARNs (state bucket, lock
    table, ECR repo, SPA bucket, bootstrap CloudFront).
  - Exits non-zero if any resource outside the allow-list appears,
    naming the offending ARNs.
- **New `scripts/print-urls.sh`**:
  - Reads `cloudfront_distribution_domain` from the bootstrap
    outputs.
  - Prints `https://<dist>.cloudfront.net/` and
    `https://<dist>.cloudfront.net/api/healthz`.
- **New `scripts/tail-logs.sh`**:
  - Uses `aws logs tail /nica-erp/api --follow --since 5m` (the AWS
    CLI has the `tail` command natively).
- **New `scripts/check-credentials.sh`**:
  - Runs `aws sts get-caller-identity` and verifies the account ID
    matches an expected `AWS_ACCOUNT_ID` env var if set; otherwise
    just prints the caller identity.
- **New `scripts/confirm-destroy.sh`**:
  - Helper sourced by `destroy.sh` and `destroy-bootstrap.sh` (in
    `add-terraform-state-backend`) — interactive `read -r` of a
    confirmation string. Avoids re-implementing the prompt twice.
- **GitHub Actions workflows for the deploy/destroy cycle** (sprint
  01 §Operations + ADR-0030 — the deploy cycle moves to CI because
  the administrator's Apple Silicon host cannot build the production
  image under QEMU emulation; the bootstrap/destroy-bootstrap cycle
  stays operator-host-side because it owns the IAM/OIDC plumbing that the
  workflows would otherwise need to exist before they can run):
  - **New `.github/workflows/deploy.yml`** — `workflow_dispatch`
    only, no `push:` trigger. Assumes `nica-erp-ci-deploy` via OIDC
    (the role is created by `add-terraform-state-backend`). Body:
    build + push image; `terraform apply` on the ephemeral root;
    `scripts/run-migrations.sh`; ECS `update-service
    --force-new-deployment`; `scripts/deploy-web.sh`; poll
    `/api/healthz` until `db: "ok"`. Emits a step summary with the
    pushed tag, alembic revision, CloudFront URL, and ECS task
    definition ARN.
  - **New `.github/workflows/destroy.yml`** — `workflow_dispatch`
    only, requires a `confirm=nica-erp-ephemeral` input. Assumes
    `nica-erp-ci-destroy` via OIDC. Body: `terraform destroy` on
    the ephemeral root; optional `clean_web_assets` input that
    empties the SPA bucket; `verify-destroyed.sh` as a report
    (not a gate).
  - Auto-trigger on `push: branches: [main]` is intentionally
    not enabled. Switching it on later is a one-line YAML diff in
    `deploy.yml`; the IAM role already trusts that ref.
- **Makefile target surface** (extends what
  `add-terraform-state-backend` and `add-api-container-image`
  shipped):
  - `deploy` → `gh workflow run deploy.yml --ref main` (NOT
    `scripts/deploy.sh` directly — the script body now runs inside
    the workflow on `ubuntu-latest`).
  - `destroy` → `gh workflow run destroy.yml --ref main -f confirm=nica-erp-ephemeral`
    (NOT `scripts/destroy.sh` directly).
  - `plan` → `terraform -chdir=infra/terraform/envs/demo plan`
    (operator-host-side read-only helper).
  - `logs` → `scripts/tail-logs.sh` (operator-host-side read-only
    helper).
  - `urls` → `scripts/print-urls.sh` (operator-host-side read-only
    helper).
  - `wipe` → `destroy` + `destroy-bootstrap` chained
    (project-close operation; the second sub-target is
    operator-host-side per `add-terraform-state-backend`).
  - `help` (already exists) extended to list the new targets.

## Capabilities

### New Capabilities

- `deploy-pipeline`: `.github/workflows/deploy.yml`, the
  orchestration scripts it invokes (`build-and-push-image.sh`,
  `run-migrations.sh`, `deploy-web.sh`), and the
  `make deploy` Makefile target that dispatches the workflow via
  `gh workflow run`. Includes the migration-run-task step, the
  forced ECS service redeploy, the post-deploy `/api/healthz`
  poll, the OIDC auth contract, and the `workflow_dispatch`-only
  trigger.
- `destroy-pipeline`: `.github/workflows/destroy.yml`,
  `verify-destroyed.sh`, `confirm-destroy.sh` (still used by the
  operator-host-side `destroy-bootstrap.sh`), plus the
  `make destroy` Makefile target that dispatches the workflow with
  the `confirm=nica-erp-ephemeral` input pre-filled, and the rule
  that `make wipe` chains the remote `destroy` workflow with the
  operator-host-side `destroy-bootstrap`.
- `web-deploy-pipeline`: the `deploy-web.sh` script, the
  `VITE_API_BASE_URL=/api` build-time convention, the
  `apps/web/.env.production` file, and the CloudFront invalidation
  step.
- `operator-diagnostics`: the `tail-logs.sh`, `print-urls.sh`,
  `check-credentials.sh` scripts and their Makefile targets
  (`logs`, `urls`).

### Modified Capabilities

- `api-bootstrap`: the existing CORS requirement SHALL be modified
  so that `bootstrap.api.create_app()` does **not** mount
  `CORSMiddleware` when `app_env == "aws"`, and the existing
  requirement about default origins SHALL be modified so that
  `CORS_ORIGINS` defaults to `[]` in that environment.

## Impact

- Affected code: `apps/api/src/bootstrap/settings.py`,
  `apps/api/src/bootstrap/api.py`,
  `apps/api/tests/unit/test_app_env_cors.py` (new),
  `apps/web/.env.production` (new),
  `apps/web/.env.local.example` (touched if it does not already
  document `VITE_API_BASE_URL`), `Makefile`,
  `scripts/{deploy,destroy,run-migrations,deploy-web,verify-destroyed,print-urls,tail-logs,check-credentials,confirm-destroy}.sh`.
- Affected APIs: `GET /api/healthz` (and every other `/api/*`
  route) SHALL be reachable through CloudFront on AWS without any
  CORS preflight; locally the existing CORS behavior is preserved.
- Dependencies: requires `pnpm` on the operator host (already
  required for `apps/web/`) and AWS CLI v2 (already required by
  earlier scripts). No new Python/Node runtime dependencies.
- Systems: no new AWS resources beyond what
  `add-aws-runtime-stack` provisioned; this change exclusively wraps
  the existing surface in scripts and Makefile targets, plus a
  small code change to the API and a config change to the SPA build.
- Out of scope (intentionally): a GitHub Actions deploy workflow
  ([ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md) — no CI/CD in
  the MVP); CloudFront cache invalidation strategies beyond `/*`
  on every web deploy (could optimise later); rollback automation
  beyond redeploying a previous image tag manually.
