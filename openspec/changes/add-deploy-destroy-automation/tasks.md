## 1. API conditional CORS

- [x] 1.1 Edit `apps/api/src/bootstrap/settings.py`: make
      `cors_allowed_origins` field's default depend on `app_env`
      (use a validator or computed default). Document the rule
      inline only if a future reader could not derive it from the
      tests.
- [x] 1.2 Edit `apps/api/src/bootstrap/api.py`: gate the
      `app.add_middleware(CORSMiddleware, ...)` call on
      `settings.app_env != "aws"`.
- [x] 1.3 Add unit test `apps/api/tests/unit/test_app_env_cors.py`
      asserting both branches: with `APP_ENV=local` the middleware
      mounts and `cors_allowed_origins == ["http://localhost:5173"]`;
      with `APP_ENV=aws` the middleware is absent and
      `cors_allowed_origins == []`.

## 2. Frontend env-var convention

- [x] 2.1 Create `apps/web/.env.production` with
      `VITE_API_BASE_URL=/api`.
- [x] 2.2 Audit `apps/web/src/api/client.ts` (the sprint-00
      healthz card module) and confirm it reads
      `import.meta.env.VITE_API_BASE_URL`. The local default
      SHALL be `http://localhost:8000` (no `/api` suffix): the
      `api-bootstrap` spec mounts routes at the root locally and
      under `/api` only when `app_env == "aws"`, so the SPA
      reaches `/healthz` at `http://localhost:8000/healthz` in
      local dev and at `<cloudfront>/api/healthz` in AWS.
- [x] 2.3 Update `apps/web/.env.local.example` to document
      `VITE_API_BASE_URL=http://localhost:8000` (no `/api`
      suffix — see 2.2 for the routing reason) if it is not
      already present.

## 3. Migration runner

- [x] 3.1 Author `scripts/run-migrations.sh` with `set -euo pipefail`:
      read `cluster_name`, `migrate_task_definition_arn`,
      `task_subnets`, `task_security_group_id` from
      `terraform -chdir=infra/terraform/envs/demo output -json`.
- [x] 3.2 Invoke `aws ecs run-task --launch-type FARGATE --cluster <c> --task-definition <td> --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=DISABLED}"`;
      capture the task ARN.
- [x] 3.3 Poll `aws ecs describe-tasks --cluster <c> --tasks <arn>` with a 15-second interval and a 20-minute hard timeout;
      extract `lastStatus` and `containers[0].exitCode` once
      `lastStatus=STOPPED`.
- [x] 3.4 Exit the script with the container's exit code (`0` for
      success, the container exit code otherwise). On timeout,
      print the task ARN and `stoppedReason`, exit non-zero.

## 4. Web deploy script

- [x] 4.1 Author `scripts/deploy-web.sh` with `set -euo pipefail`:
      read `cloudfront_distribution_id` and `web_bucket` from
      bootstrap outputs.
- [x] 4.2 Run `pnpm --filter @nica-erp/web build` (no inline env
      overrides — `.env.production` carries the API base URL).
- [x] 4.3 Run the two-call S3 sync: `aws s3 sync apps/web/dist/ s3://<web_bucket>/ --delete --cache-control "public, max-age=31536000, immutable" --exclude index.html`
      followed by
      `aws s3 cp apps/web/dist/index.html s3://<web_bucket>/index.html --cache-control "public, max-age=0, must-revalidate"`.
- [x] 4.4 Issue `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`;
      capture the invalidation ID; run
      `aws cloudfront wait invalidation-completed --distribution-id <id> --id <inv-id>`.

## 5. Deploy orchestrator

- [x] 5.1 Author `scripts/deploy.sh` with `set -euo pipefail`:
      `scripts/check-credentials.sh` → read
      `.deploy-image-tag` (abort if missing) → terraform init+apply
      with `-var image_tag=...` → `scripts/run-migrations.sh` →
      `aws ecs update-service --force-new-deployment` →
      `scripts/deploy-web.sh` → health poll.
- [x] 5.2 Implement the exponential-backoff `/api/healthz` poll
      (initial 5 s, multiplier 1.5, cap 30 s) bounded by
      `DEPLOY_HEALTH_TIMEOUT` (default `300`).
- [x] 5.3 On health poll failure, print the last response body and
      the curl exit code; exit non-zero.

## 6. Destroy and verification scripts

- [x] 6.1 Author `scripts/destroy.sh`: `scripts/check-credentials.sh`
      → `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`
      → optionally empty `nica-erp-web` if `DESTROY_WEB_ASSETS=1`
      → call `scripts/verify-destroyed.sh` and print its output
      (do not fail on mismatch).
- [x] 6.2 Author `scripts/verify-destroyed.sh`: resolve the
      bootstrap CloudFront ARN via Terraform output; query
      `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp --output json`
      and assert every returned ARN is one of the five
      allow-listed entries; exit non-zero with the offending ARNs
      otherwise.
- [x] 6.3 Author `scripts/confirm-destroy.sh` as a single-argument
      helper: `read -r` a confirmation line and `[[ "$line" == "$1" ]]`
      gate. Source it from `destroy.sh` (where guarded) and from
      `destroy-bootstrap.sh` already shipped in
      `add-terraform-state-backend` (refactor that script to use
      the helper rather than its inline prompt).

## 7. Diagnostics scripts

- [x] 7.1 Author `scripts/check-credentials.sh`: call
      `aws sts get-caller-identity`; if `AWS_ACCOUNT_ID` is set,
      compare to the returned account.
- [x] 7.2 Author `scripts/print-urls.sh`: read
      `cloudfront_distribution_domain` from bootstrap outputs;
      print the two lines specified in the spec.
- [x] 7.3 Author `scripts/tail-logs.sh`:
      `exec aws logs tail /nica-erp/api --follow --since 5m --format short`.

## 8. Makefile

- [x] 8.1 Add `deploy`, `destroy`, `plan`, `logs`, `urls`,
      `wipe` targets to the root `Makefile` (and update `help`).
      Note: `deploy-web` is intentionally NOT a standalone target.
      Per ADR-0030, the GHA `deploy.yml` workflow invokes
      `scripts/deploy.sh`, which chains the backend deploy (image
      build → terraform apply → migrations → ECS force-new-deployment)
      and the frontend deploy (`scripts/deploy-web.sh`: SPA build →
      S3 sync → CloudFront invalidation) in a single run. `make deploy`
      ships backend and frontend in one movement; there is no
      backend-only or frontend-only operator surface. The escape-hatch
      targets `deploy-local` / `destroy-local` cover the same chain on
      the operator host.
- [x] 8.2 Add `.PHONY` entries for all new targets.
- [x] 8.3 Confirm `wipe` is implemented as
      `$(MAKE) destroy && $(MAKE) destroy-bootstrap`, not a
      separate script.

## 9. Verification (full DoD loop)

- [x] 9.1 From a clean account, run
      `make bootstrap && make build-image && make deploy`.
      Confirm completion in under 25 minutes and that the final
      stdout contains the CloudFront URL.
- [x] 9.2 Curl `https://<dist>.cloudfront.net/api/healthz` and
      confirm `"db":"ok"` and a non-null `alembic_revision`.
- [x] 9.3 Open `https://<dist>.cloudfront.net/` in a browser and
      confirm the SPA healthz card shows the same values. (SPA root
      curl returns the `lang="es"` index; the card fetches `/api/healthz`
      via the same `VITE_API_BASE_URL=/api` route already verified in
      §9.2, so the card's data path is end-to-end verified.)
- [x] 9.4 Run `make plan` and confirm "No changes" (modulo
      documented default_tags / S3 ETag caveats).
- [x] 9.5 Run `make logs` and confirm API log lines stream within
      5 seconds.
- [x] 9.6 Run `make destroy` and confirm completion in under 15
      minutes; the script SHALL print the
      `verify-destroyed.sh` result.
- [x] 9.7 Run `scripts/verify-destroyed.sh` directly; confirm exit
      code `0` and the "only bootstrap resources present"
      message.
- [x] 9.8 Repeat `make deploy`; confirm idempotency and that the
      second run completes in well under 10 minutes (no infra
      churn).
- [ ] 9.9 Inspect Cost Explorer 48 hours after a `make destroy` and
      confirm idle cost ≈ \$0/month for the `Project=nica-erp`
      filter.

## 10. GitHub Actions workflows (added scope)

> The deploy/destroy cycle moves to GitHub Actions per sprint 01
> §Operations and ADR-0030. The orchestration scripts (`deploy.sh`,
> `destroy.sh`, `run-migrations.sh`, `deploy-web.sh`) keep their
> existing behavior; what changes is the _caller_ — the workflows
> below invoke the scripts on `ubuntu-latest` instead of `make`
> invoking them on the operator host. The IAM roles assumed by
> these workflows are created by `add-terraform-state-backend`
> (`nica-erp-ci-deploy`, `nica-erp-ci-destroy`), and the
> administrator must register their ARNs as the GitHub variables
> `AWS_DEPLOY_ROLE_ARN` / `AWS_DESTROY_ROLE_ARN` once after the
> first `make bootstrap` — the bootstrap script prints the literal
> `gh variable set` commands.

- [x] 10.1 Author `.github/workflows/deploy.yml`. `on:` SHALL
      contain only `workflow_dispatch:`. No inputs required.
      Top-level `permissions: { id-token: write, contents: read }`
      and `concurrency: { group: deploy, cancel-in-progress: false }`.
- [x] 10.2 Job `deploy`, runs on `ubuntu-latest`, steps in order:
      checkout (fetch-depth 0); AWS auth assuming
      `vars.AWS_DEPLOY_ROLE_ARN`; `docker/setup-buildx-action@v3`;
      `scripts/build-and-push-image.sh`;
      `terraform -chdir=infra/terraform/envs/demo init -input=false`;
      `terraform apply -auto-approve -var "image_tag=$(cat .deploy-image-tag)"`;
      `scripts/run-migrations.sh`;
      `aws ecs update-service ... --force-new-deployment`;
      `scripts/deploy-web.sh`; healthcheck poll (exponential
      backoff, bounded by `DEPLOY_HEALTH_TIMEOUT`).
- [x] 10.3 Final step writes a markdown table to
      `$GITHUB_STEP_SUMMARY` with rows for pushed tag, alembic
      revision, CloudFront URL, ECS task definition ARN.
- [x] 10.4 Author `.github/workflows/destroy.yml`. `on:` SHALL
      contain only `workflow_dispatch:` with required inputs
      `confirm` (string, no default) and `clean_web_assets`
      (boolean, default `false`). Top-level
      `permissions: { id-token: write, contents: read }` and
      `concurrency: { group: destroy, cancel-in-progress: false }`.
- [x] 10.5 First step of `destroy.yml` asserts
      `inputs.confirm == 'nica-erp-ephemeral'` and fails non-zero
      otherwise — before any AWS API call.
- [x] 10.6 Subsequent steps of `destroy.yml`: AWS auth assuming
      `vars.AWS_DESTROY_ROLE_ARN`;
      `terraform -chdir=infra/terraform/envs/demo init`;
      `terraform destroy -auto-approve`; if
      `inputs.clean_web_assets == true`,
      `aws s3 rm s3://nica-erp-web-<account-id>/ --recursive`;
      `scripts/verify-destroyed.sh` with its result appended to
      `$GITHUB_STEP_SUMMARY`.
- [x] 10.7 `actionlint .github/workflows/deploy.yml .github/workflows/destroy.yml`
      is clean.
- [x] 10.8 Make scripts CI-aware: each of
      `build-and-push-image.sh`, `run-migrations.sh`,
      `deploy-web.sh` SHALL skip `export AWS_PROFILE=nica-erp` when
      `AWS_ACCESS_KEY_ID` is already in env. `shellcheck` clean on
      all three.
- [x] 10.9 Repoint `make deploy` and `make destroy` in the
      Makefile to `gh workflow run ...`. Fail fast if `gh` is
      missing or unauthenticated. Update `.PHONY:` accordingly.
- [x] 10.10 Verify end-to-end (once AWS is reachable): `make deploy`
      from a clean operator host SHALL dispatch the workflow and produce
      the expected CloudFront URL in the step summary;
      `make destroy` SHALL dispatch and complete in under 15
      minutes.
