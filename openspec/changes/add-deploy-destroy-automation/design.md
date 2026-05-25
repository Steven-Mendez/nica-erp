## Context

`add-terraform-state-backend`, `add-api-container-image`, and
`add-aws-runtime-stack` between them already make a full deploy
*possible*. What's left is to make it *cheap to repeat*. Sprint 01
explicitly puts deploy/destroy in the DoD
([ADR-0018](../../../docs/adr/0018-rolling-deploys.md)) — every
future sprint will end with the operator running `make destroy` and
later `make deploy`. If those commands are awkward or hide failure
modes, the whole rolling-deploys promise breaks.

This change also closes the last two application-side seams sprint
01 opened:

- The API needs to know it is running in AWS so it can drop the
  CORS middleware. Same-origin CloudFront makes CORS dead weight at
  best and a foot-gun at worst (a misconfigured `Access-Control-Allow-Origin`
  would shadow real configuration bugs).
- The SPA needs to know its API lives at `/api`, not at
  `http://localhost:8000`. This is a build-time decision in Vite,
  not a runtime decision in the browser.

The interesting design work is in the orchestration: in which order
do migrations / image deploy / SPA deploy / CloudFront invalidation
happen, and how do failures in one step prevent the others from
declaring success?

## Goals / Non-Goals

**Goals:**

- `make deploy` brings the AWS environment from "post-destroy" to
  "healthz returns ok" in one command, including running migrations
  and refreshing the SPA. Failures in any step abort and report
  diagnosable output.
- `make destroy` tears down every ephemeral resource and is the
  command an operator runs unattended at end of day. `make wipe`
  exists for the rare project-close operation that also removes the
  bootstrap.
- `verify-destroyed.sh` is the trustworthy authority on "did we
  really go back to ≈$0/month" — the answer must not depend on the
  operator's memory.
- Local development stays exactly as it was after sprint 00. The
  AWS branch of the API toggle is gated by `app_env=aws`; nothing
  else changes.
- `make deploy` from a clean clone runs in under ~25 minutes
  including the ~5 minutes CloudFront propagation budget. The
  steady-state redeploy (image already in ECR, infra unchanged)
  runs in under 10 minutes.

**Non-Goals:**

- CI/CD via GitHub Actions
  ([ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md)). The deploy
  remains operator-triggered.
- Blue/green or canary deployment of the API service. Rolling at
  `min=100%/max=200%` is enough for the MVP.
- Selective CloudFront invalidations
  (`/index.html`, `/assets/...`). Full `/*` invalidation is fine at
  the volume of one SPA build per deploy.
- A rollback automation. "Rollback" in MVP terms is "set
  `image_tag` to a previous SHA and re-run `make deploy`."
- Cross-account or multi-environment (staging/prod) Make targets.
  Sprint 01 ships demo only.

## Decisions

### Deploy order: terraform → migrations → service force-redeploy → web → poll

The ordering matters in non-obvious ways:

1. **Terraform first** lands any infrastructure changes (new IAM
   permissions, new SSM parameters, new env vars on the task
   definition). Anything else assumes the infra is current.
2. **Migrations next**, before the API service picks up the new
   image. Running migrations *after* the service is updated means
   live tasks would be hitting a database that doesn't yet have
   their expected schema. Running them through the dedicated
   `nica-erp-migrate` task definition keeps the API IAM surface
   minimal — the long-running tasks never had `CREATE TABLE`-level
   privileges anyway.
3. **Force-redeploy** the ECS service: when `terraform apply`
   updates a task-definition revision, the service automatically
   picks it up. But when `image_tag` is the same value (an
   operator re-running `make deploy` after a one-line config
   tweak), Terraform sees no change and the service doesn't
   refresh. `aws ecs update-service --force-new-deployment` always
   cycles the tasks.
4. **Web deploy**: SPA can be uploaded any time after the bootstrap
   CloudFront exists; doing it after the API redeploy means the
   `/healthz` card the SPA shows lines up with the API the user
   just deployed.
5. **Poll** `/api/healthz` until it returns `db:"ok"`. CloudFront
   takes ~5 minutes to propagate origin changes after a fresh
   `add-aws-runtime-stack` apply; on a steady-state redeploy the
   wait is closer to 30 s for the new ECS task to become healthy.

Alternative considered: parallelise migrations with the SPA build.
Rejected — adds bash complexity for a ~30s win.

### Migration runner returns the task's exit code

`run-migrations.sh` uses `aws ecs run-task ... --query 'tasks[0].taskArn' --output text`
to capture the task ARN, then polls `aws ecs describe-tasks` for
`lastStatus=STOPPED`. The script extracts
`containers[0].exitCode` and exits with that value.

Rationale: an alembic failure must propagate so `make deploy` fails
loudly. Without this, a broken migration silently leaves the API
behind on the old schema and the operator only notices when
`/healthz` reports a wrong revision.

### `force-new-deployment` is unconditional

Even when the task-definition revision did change (typical case
after a new `image_tag`), an unconditional
`update-service --force-new-deployment` is a no-op for the
state-change check but still cycles tasks. The cost is one extra
API call.

Rationale: branching on "did terraform actually change the
revision" is bash glue we don't want to maintain.

### CloudFront cache headers: aggressive on `/assets/`, none on `index.html`

`aws s3 sync` with
`--cache-control "public, max-age=31536000, immutable"` is applied
to everything in `apps/web/dist/assets/` (which Vite hashes
content-by-content; the file names already cache-bust). A second
`aws s3 cp index.html ... --cache-control "public, max-age=0, must-revalidate"`
overrides the cache for the SPA shell so a deploy's `index.html`
shows up immediately for returning users.

Rationale: standard Vite-on-CloudFront recipe.

### Single full `/*` invalidation per deploy

Each deploy issues one `aws cloudfront create-invalidation --paths "/*"`.
CloudFront charges $0 for the first 1000 paths in a month; `/*`
counts as a single path. Waiting on the invalidation
(`aws cloudfront wait invalidation-completed`) typically takes
under 60 s.

Rationale: simpler than partial invalidations and within the free
tier.

### App-env-conditional CORS, gated in `bootstrap.api.create_app()`

The toggle lives in code, not in env vars passed to
`CORSMiddleware`. `create_app()` reads `settings.app_env`; if
`"aws"`, it does not register `CORSMiddleware` at all. Locally the
behavior is unchanged: `app_env` defaults to `"local"` and the
middleware mounts with the Vite origin.

Rationale: a "mount empty middleware" pattern still serves
`Access-Control-Allow-Origin: ` headers from FastAPI / Starlette,
which is worse than no header at all — some browsers reject
ambiguous CORS preflights. Skipping the middleware entirely is the
clean answer.

Alternative considered: gating with a build-time switch. Rejected
— the same image runs locally (developer using `make local-up`
with `APP_ENV=aws` to simulate prod CORS behavior) and in AWS;
runtime is the right place.

### `VITE_API_BASE_URL=/api` lives in `apps/web/.env.production`

Vite reads `.env.production` automatically when building with
`pnpm build` (`mode=production` is the default). Committing this
file means `deploy-web.sh` doesn't need to inject env vars at
build time; the convention is reproducible across operators.

Rationale: matches the Vite-documented configuration model.

### `verify-destroyed.sh` allow-list is hard-coded

The script ships a hard-coded list of the four bootstrap resource
ARNs the operator may legitimately see post-destroy. Anything else
tagged `Project=nica-erp` fails the check.

Rationale: a generic "ignore anything matching a pattern" check is
too forgiving. Each new persistent resource added in a later
sprint will explicitly update this allow-list, which is a deliberate
review-time decision.

### `wipe` is a Makefile chain, not a separate script

`wipe` simply runs `make destroy` then `make destroy-bootstrap`. No
new script. The chain operates at the Make layer because each
sub-target has its own confirmation prompt
(`destroy-bootstrap` requires the literal `nica-erp-bootstrap`
string from `add-terraform-state-backend`). Composing at the script
layer would swallow those prompts.

### Idempotent `make deploy` and `make destroy`

Re-running `make deploy` against an already-deployed environment
is a Terraform no-op + a migration that exits successfully on
`alembic upgrade head` already-at-head + a redeploy of identical
ECS tasks. Re-running `make destroy` against an already-destroyed
environment exits 0 (Terraform destroy is idempotent).

Rationale: an operator should never have to ask "did the previous
deploy finish?" before running another.

## Risks / Trade-offs

- **Risk**: A migration that runs forever (or hangs in
  `PROVISIONING`) blocks the deploy. → **Mitigation**: the runner
  polls with a 20-minute hard timeout; on timeout it exits non-zero
  and prints the task ARN so the operator can inspect via
  CloudWatch Logs / ECS console.
- **Risk**: Force-redeploying with a broken image leaves the
  service in `desiredCount=1, runningCount=0` while the deployment
  health check fails. → **Mitigation**: ECS deployment
  circuit breaker (`enable=true, rollback=true`) reverts to the
  previous revision automatically; the post-deploy `/healthz` poll
  catches the failure and reports it.
- **Risk**: The `/healthz` poll's exponential backoff masks slow
  but eventually-successful deploys as failures. → **Mitigation**:
  cap the total wait at ~5 minutes plus a documented option to
  raise it via `DEPLOY_HEALTH_TIMEOUT=600 make deploy`.
- **Risk**: `verify-destroyed.sh` allow-list drift: a new
  persistent resource added in a later sprint without updating the
  script will fail every destroy verification until the script is
  updated. → **Trade-off**: accepted; this is the intended review
  gate.
- **Risk**: `--cache-control immutable` on hashed assets caches a
  bad build for a year if Vite's hashing collides (extremely
  unlikely). → **Mitigation**: full `/*` invalidation on every
  deploy purges any cached bad asset within ~60 s.
- **Risk**: `make destroy` runs against the wrong AWS account. →
  **Mitigation**: `check-credentials.sh` is invoked at the top of
  `deploy.sh` and `destroy.sh`; an unset or unexpected
  `AWS_ACCOUNT_ID` (when configured) aborts.
- **Risk**: The conditional CORS toggle hides a regression where a
  developer accidentally sets `APP_ENV=aws` locally and gets
  surprised by missing CORS headers. → **Mitigation**: a
  dedicated unit test enumerates both branches (`local` and
  `aws`) and asserts middleware mount status. A failing assertion
  catches the regression in CI.

## Migration Plan

This change has no prior automation to migrate from; the scripts
and Makefile targets are net new.

- Deploy: land this change, then run
  `make bootstrap && make build-image && make deploy` from a clean
  account. The full DoD loop validates itself.
- Rollback: `git revert` of this change leaves changes 1–3 intact
  but removes the deploy/destroy automation. Operators would fall
  back to manual Terraform invocations; not catastrophic but
  loses the rolling-deploys ergonomics.

## Open Questions

- (none — orchestration steps are pinned by sprint 01's DoD list
  and the cited ADRs)
