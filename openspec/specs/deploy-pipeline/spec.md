# deploy-pipeline Specification

## Purpose
TBD - created by archiving change add-deploy-destroy-automation. Update Purpose after archive.

## Requirements
### Requirement: `make deploy` dispatches the deploy workflow on GitHub Actions

The root `Makefile` SHALL declare a target `deploy` that invokes
`gh workflow run deploy.yml --ref main`. The target SHALL exit
non-zero with a clear diagnostic if `gh` is missing or
unauthenticated and SHALL NOT invoke `terraform`, `docker`, or any
deploy script locally. The orchestration itself runs on the GHA
runner under the `nica-erp-ci-deploy` OIDC-assumed role.

#### Scenario: `make deploy` triggers the remote workflow

- **WHEN** `make deploy` is run on a host with `gh` authenticated
- **THEN** the command SHALL invoke
  `gh workflow run deploy.yml --ref main` and SHALL NOT call
  `terraform` or `docker` locally

#### Scenario: `make deploy` fails fast if gh is missing

- **WHEN** `make deploy` is run on a host where `gh` is not on the
  PATH or `gh auth status` fails
- **THEN** the target SHALL exit non-zero with a diagnostic naming
  the missing tool or auth state, and SHALL NOT invoke any AWS
  call

### Requirement: deploy.yml orchestrates build, terraform apply, migrations, ECS redeploy, web upload, and healthcheck

`.github/workflows/deploy.yml` SHALL execute, in order, on a single
`ubuntu-latest` job:

1. `actions/checkout@v6` with `fetch-depth: 0` so
   `git rev-parse HEAD` resolves to the launching commit.
2. `aws-actions/configure-aws-credentials@v4` assuming
   `${{ vars.AWS_DEPLOY_ROLE_ARN }}` via OIDC.
3. `docker/setup-buildx-action@v3`, then
   `scripts/build-and-push-image.sh` (writes
   `.deploy-image-tag` in the runner's workspace).
4. `terraform -chdir=infra/terraform/envs/demo init -input=false`.
5. `terraform -chdir=infra/terraform/envs/demo apply -auto-approve -var "image_tag=$(cat .deploy-image-tag)"`.
6. `scripts/run-migrations.sh`. The workflow step SHALL propagate
   the migration container's exit code.
7. `aws ecs update-service --cluster nica-erp-demo --service nica-erp-api --force-new-deployment`.
8. `scripts/deploy-web.sh`.
9. Poll `https://<dist-id>.cloudfront.net/api/healthz` with
   exponential backoff (initial 5 s, multiplier 1.5, cap 30 s)
   until the response is HTTP 200 with a JSON body containing
   `"db":"ok"`. Total elapsed time SHALL be bounded by the
   workflow env `DEPLOY_HEALTH_TIMEOUT` (default `300` seconds).
10. Append a markdown table to `$GITHUB_STEP_SUMMARY` listing the
    pushed image tag, the alembic revision applied (from the
    healthcheck response), the CloudFront URL, and the new ECS
    task definition ARN.

Any non-zero exit from steps 1–8 SHALL fail the workflow
immediately. A timeout on step 9 SHALL fail the workflow with a
diagnostic naming the last healthcheck response body.

#### Scenario: Clean deploy succeeds end-to-end

- **WHEN** `gh workflow run deploy.yml --ref main` is dispatched
  against a clean working tree after `make bootstrap` and the
  initial role-ARN setup
- **THEN** the workflow SHALL complete within 25 minutes and exit
  `0`
- **AND** the run's Summary tab SHALL contain rows for the pushed
  tag, the alembic revision, the CloudFront URL, and the ECS task
  definition ARN

#### Scenario: Pushing to main does not auto-deploy

- **WHEN** a commit is pushed to the `main` branch
- **THEN** `deploy.yml` SHALL NOT be scheduled or executed by
  GitHub

### Requirement: deploy.yml authenticates via OIDC, not static keys

`deploy.yml` SHALL declare top-level
`permissions: { id-token: write, contents: read }` and SHALL use
`aws-actions/configure-aws-credentials@v4` with `role-to-assume`
pointing at the GitHub repository variable `AWS_DEPLOY_ROLE_ARN`.
It SHALL NOT reference `AWS_ACCESS_KEY_ID` or
`AWS_SECRET_ACCESS_KEY` repository secrets.

#### Scenario: No long-lived AWS keys in deploy.yml

- **WHEN** `.github/workflows/deploy.yml` is inspected
- **THEN** it SHALL contain no reference to `AWS_ACCESS_KEY_ID` or
  `AWS_SECRET_ACCESS_KEY`
- **AND** it SHALL contain `permissions: id-token: write` and an
  `aws-actions/configure-aws-credentials` invocation referencing
  `vars.AWS_DEPLOY_ROLE_ARN`

### Requirement: deploy.yml serializes concurrent dispatches

`deploy.yml` SHALL declare a `concurrency` block with
`group: deploy` and `cancel-in-progress: false`. Two simultaneous
dispatches SHALL queue rather than race; a later dispatch SHALL
NOT cancel an in-flight run.

#### Scenario: Two dispatches queue cleanly

- **WHEN** `deploy.yml` is dispatched twice in quick succession
- **THEN** the second run SHALL wait for the first to complete and
  the first SHALL run to completion uninterrupted

### Requirement: Auto-trigger on push to main is a one-line YAML diff

`deploy.yml`'s `on:` block SHALL be structured such that enabling
auto-trigger requires only adding a `push: { branches: [main] }`
sub-block (plus an appropriate `paths:` filter). No other change
to the workflow file, the IAM role, or any script SHALL be
required.

#### Scenario: Enabling push-trigger requires no infra change

- **WHEN** an administrator uncomments the `push:` sub-block of
  `deploy.yml`
- **THEN** the workflow SHALL succeed on the next push to `main`
  without any change to `nica-erp-ci-deploy`'s trust policy or
  inline policy

### Requirement: Build script and orchestration scripts are CI-aware

Every orchestration script invoked by `deploy.yml` SHALL detect
whether it is running under CI by checking whether
`AWS_ACCESS_KEY_ID` is already set in the environment.
`scripts/build-and-push-image.sh`, `scripts/run-migrations.sh`,
and `scripts/deploy-web.sh` SHALL each follow this rule: when
`AWS_ACCESS_KEY_ID` is set (the OIDC path), they SHALL NOT set
`AWS_PROFILE`; when unset (the operator-host path, used only for ad-hoc
debugging), they SHALL set `AWS_PROFILE=nica-erp` per the project's
AWS profile convention.

#### Scenario: CI run does not pin AWS_PROFILE

- **WHEN** any orchestration script runs with `AWS_ACCESS_KEY_ID`
  already in env
- **THEN** the script SHALL NOT export `AWS_PROFILE=nica-erp`
- **AND** `aws sts get-caller-identity` SHALL use the env
  credentials

### Requirement: Migration runner exits with the container's exit code

`scripts/run-migrations.sh` SHALL invoke `aws ecs run-task` against
the `nica-erp-migrate` task definition (resolved from
`terraform -chdir=infra/terraform/envs/demo output -raw migrate_task_definition_arn`)
with `launch-type=FARGATE`, `network-configuration` referencing
the private subnets and `sg_ecs_tasks` from the same outputs. The
script SHALL capture the resulting task ARN, poll
`aws ecs describe-tasks` until `lastStatus=STOPPED`, and exit with
the container's `exitCode`.

#### Scenario: Successful migration exits 0

- **WHEN** `scripts/run-migrations.sh` is invoked and Alembic's
  `upgrade head` succeeds
- **THEN** the script SHALL exit `0` and the stdout SHALL include
  the task ARN

#### Scenario: Failed migration propagates non-zero exit

- **WHEN** the migration container exits with code `1`
- **THEN** `scripts/run-migrations.sh` SHALL exit `1` and the
  stdout SHALL include the task ARN and the `stoppedReason` field

#### Scenario: Migration timeout aborts cleanly

- **WHEN** the migration task remains in `PROVISIONING` or
  `RUNNING` for longer than 20 minutes
- **THEN** the script SHALL exit non-zero with a diagnostic naming
  the task ARN and the workflow SHALL NOT proceed to the ECS
  `update-service --force-new-deployment` step

### Requirement: Forced ECS service redeploy is unconditional

The deploy workflow SHALL invoke
`aws ecs update-service --cluster nica-erp-demo --service nica-erp-api --force-new-deployment`
on every successful run, regardless of whether `terraform apply`
reported task-definition changes. The redeploy SHALL be issued
**after** `run-migrations.sh` succeeds and **before**
`deploy-web.sh` runs.

#### Scenario: Redeploy issues even when terraform reports no changes

- **WHEN** `deploy.yml` is dispatched a second time with no
  changes since the previous successful deploy
- **THEN** the AWS CloudTrail event log SHALL show one
  `UpdateService` API call with `forceNewDeployment=true`
