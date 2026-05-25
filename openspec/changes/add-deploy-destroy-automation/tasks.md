## 1. API conditional CORS

- [ ] 1.1 Edit `apps/api/src/bootstrap/settings.py`: make
      `cors_allowed_origins` field's default depend on `app_env`
      (use a validator or computed default). Document the rule
      inline only if a future reader could not derive it from the
      tests.
- [ ] 1.2 Edit `apps/api/src/bootstrap/api.py`: gate the
      `app.add_middleware(CORSMiddleware, ...)` call on
      `settings.app_env != "aws"`.
- [ ] 1.3 Add unit test `apps/api/tests/unit/test_app_env_cors.py`
      asserting both branches: with `APP_ENV=local` the middleware
      mounts and `cors_allowed_origins == ["http://localhost:5173"]`;
      with `APP_ENV=aws` the middleware is absent and
      `cors_allowed_origins == []`.

## 2. Frontend env-var convention

- [ ] 2.1 Create `apps/web/.env.production` with
      `VITE_API_BASE_URL=/api`.
- [ ] 2.2 Audit `apps/web/src/lib/api.ts` (or the equivalent module
      the sprint-00 healthz card already uses) and confirm it
      reads `import.meta.env.VITE_API_BASE_URL`. If not, refactor
      to use it with a local default of
      `http://localhost:8000/api`.
- [ ] 2.3 Update `apps/web/.env.local.example` to document
      `VITE_API_BASE_URL=http://localhost:8000/api` if it is not
      already present.

## 3. Migration runner

- [ ] 3.1 Author `scripts/run-migrations.sh` with `set -euo pipefail`:
      read `cluster_name`, `migrate_task_definition_arn`,
      `task_subnets`, `task_security_group_id` from
      `terraform -chdir=infra/terraform/envs/demo output -json`.
- [ ] 3.2 Invoke `aws ecs run-task --launch-type FARGATE --cluster <c> --task-definition <td> --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=DISABLED}"`;
      capture the task ARN.
- [ ] 3.3 Poll `aws ecs describe-tasks --cluster <c> --tasks <arn>` with a 15-second interval and a 20-minute hard timeout;
      extract `lastStatus` and `containers[0].exitCode` once
      `lastStatus=STOPPED`.
- [ ] 3.4 Exit the script with the container's exit code (`0` for
      success, the container exit code otherwise). On timeout,
      print the task ARN and `stoppedReason`, exit non-zero.

## 4. Web deploy script

- [ ] 4.1 Author `scripts/deploy-web.sh` with `set -euo pipefail`:
      read `cloudfront_distribution_id` and `web_bucket` from
      bootstrap outputs.
- [ ] 4.2 Run `pnpm --filter @nica-erp/web build` (no inline env
      overrides — `.env.production` carries the API base URL).
- [ ] 4.3 Run the two-call S3 sync: `aws s3 sync apps/web/dist/ s3://<web_bucket>/ --delete --cache-control "public, max-age=31536000, immutable" --exclude index.html`
      followed by
      `aws s3 cp apps/web/dist/index.html s3://<web_bucket>/index.html --cache-control "public, max-age=0, must-revalidate"`.
- [ ] 4.4 Issue `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`;
      capture the invalidation ID; run
      `aws cloudfront wait invalidation-completed --distribution-id <id> --id <inv-id>`.

## 5. Deploy orchestrator

- [ ] 5.1 Author `scripts/deploy.sh` with `set -euo pipefail`:
      `scripts/check-credentials.sh` → read
      `.deploy-image-tag` (abort if missing) → terraform init+apply
      with `-var image_tag=...` → `scripts/run-migrations.sh` →
      `aws ecs update-service --force-new-deployment` →
      `scripts/deploy-web.sh` → health poll.
- [ ] 5.2 Implement the exponential-backoff `/api/healthz` poll
      (initial 5 s, multiplier 1.5, cap 30 s) bounded by
      `DEPLOY_HEALTH_TIMEOUT` (default `300`).
- [ ] 5.3 On health poll failure, print the last response body and
      the curl exit code; exit non-zero.

## 6. Destroy and verification scripts

- [ ] 6.1 Author `scripts/destroy.sh`: `scripts/check-credentials.sh`
      → `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`
      → optionally empty `nica-erp-web` if `DESTROY_WEB_ASSETS=1`
      → call `scripts/verify-destroyed.sh` and print its output
      (do not fail on mismatch).
- [ ] 6.2 Author `scripts/verify-destroyed.sh`: resolve the
      bootstrap CloudFront ARN via Terraform output; query
      `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp --output json`
      and assert every returned ARN is one of the five
      allow-listed entries; exit non-zero with the offending ARNs
      otherwise.
- [ ] 6.3 Author `scripts/confirm-destroy.sh` as a single-argument
      helper: `read -r` a confirmation line and `[[ "$line" == "$1" ]]`
      gate. Source it from `destroy.sh` (where guarded) and from
      `destroy-bootstrap.sh` already shipped in
      `add-terraform-state-backend` (refactor that script to use
      the helper rather than its inline prompt).

## 7. Diagnostics scripts

- [ ] 7.1 Author `scripts/check-credentials.sh`: call
      `aws sts get-caller-identity`; if `AWS_ACCOUNT_ID` is set,
      compare to the returned account.
- [ ] 7.2 Author `scripts/print-urls.sh`: read
      `cloudfront_distribution_domain` from bootstrap outputs;
      print the two lines specified in the spec.
- [ ] 7.3 Author `scripts/tail-logs.sh`:
      `exec aws logs tail /nica-erp/api --follow --since 5m --format short`.

## 8. Makefile

- [ ] 8.1 Add `deploy`, `destroy`, `plan`, `logs`, `urls`,
      `deploy-web`, `wipe` targets to the root `Makefile` (and
      update `help`).
- [ ] 8.2 Add `.PHONY` entries for all new targets.
- [ ] 8.3 Confirm `wipe` is implemented as
      `$(MAKE) destroy && $(MAKE) destroy-bootstrap`, not a
      separate script.

## 9. Verification (full DoD loop)

- [ ] 9.1 From a clean account, run
      `make bootstrap && make build-image && make deploy`.
      Confirm completion in under 25 minutes and that the final
      stdout contains the CloudFront URL.
- [ ] 9.2 Curl `https://<dist>.cloudfront.net/api/healthz` and
      confirm `"db":"ok"` and a non-null `alembic_revision`.
- [ ] 9.3 Open `https://<dist>.cloudfront.net/` in a browser and
      confirm the SPA healthz card shows the same values.
- [ ] 9.4 Run `make plan` and confirm "No changes" (modulo
      documented default_tags / S3 ETag caveats).
- [ ] 9.5 Run `make logs` and confirm API log lines stream within
      5 seconds.
- [ ] 9.6 Run `make destroy` and confirm completion in under 15
      minutes; the script SHALL print the
      `verify-destroyed.sh` result.
- [ ] 9.7 Run `scripts/verify-destroyed.sh` directly; confirm exit
      code `0` and the "only bootstrap resources present"
      message.
- [ ] 9.8 Repeat `make deploy`; confirm idempotency and that the
      second run completes in well under 10 minutes (no infra
      churn).
- [ ] 9.9 Inspect Cost Explorer 48 hours after a `make destroy` and
      confirm idle cost ≈ \$0/month for the `Project=nica-erp`
      filter.
