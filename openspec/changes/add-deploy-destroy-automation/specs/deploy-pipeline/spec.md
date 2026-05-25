## ADDED Requirements

### Requirement: `make deploy` orchestrates terraform, migrations, ECS redeploy, web, and healthcheck

The root `Makefile` SHALL declare a target `deploy` that delegates
to `scripts/deploy.sh`. The script SHALL execute, in order:

1. `scripts/check-credentials.sh`.
2. Read `.deploy-image-tag` and exit non-zero with a message
   instructing `make build-image` if the file is missing.
3. `terraform -chdir=infra/terraform/envs/demo init -input=false`.
4. `terraform -chdir=infra/terraform/envs/demo apply -auto-approve -var "image_tag=$(cat .deploy-image-tag)"`.
5. `scripts/run-migrations.sh`. The script SHALL propagate the
   migration container's exit code.
6. `aws ecs update-service --cluster nica-erp-demo --service nica-erp-api --force-new-deployment`.
7. `scripts/deploy-web.sh`.
8. Poll `https://<dist-id>.cloudfront.net/api/healthz` with
   exponential backoff (initial 5 s, multiplier 1.5, cap 30 s)
   until the response is HTTP 200 with a JSON body containing
   `"db":"ok"`. Total elapsed time SHALL be bounded by
   `DEPLOY_HEALTH_TIMEOUT` (default `300` seconds).

Any non-zero exit from steps 1–7 SHALL abort the script with that
exit code. A timeout on step 8 SHALL exit non-zero with a
diagnostic naming the last response body.

#### Scenario: Clean deploy returns success

- **WHEN** an operator runs `make deploy` after `make bootstrap`
  and `make build-image`
- **THEN** the script SHALL complete within 25 minutes and exit `0`
- **AND** the final stdout line SHALL contain
  `https://<dist-id>.cloudfront.net/api/healthz`

#### Scenario: Missing image tag aborts before terraform

- **WHEN** `make deploy` is run without `.deploy-image-tag` present
- **THEN** the script SHALL exit non-zero, the message SHALL
  reference `make build-image`, and no `terraform apply` SHALL
  have been issued

### Requirement: Migration runner exits with the container's exit code

`scripts/run-migrations.sh` SHALL invoke `aws ecs run-task` against
the `nica-erp-migrate` task definition (resolved from
`terraform -chdir=infra/terraform/envs/demo output -raw migrate_task_definition_arn`)
with `launch-type=FARGATE`, `network-configuration` referencing the
private subnets and `sg_ecs_tasks` from the same outputs. The
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
  stdout SHALL include the task ARN and the
  `stoppedReason` field

#### Scenario: Migration timeout aborts cleanly

- **WHEN** the migration task remains in `PROVISIONING` or `RUNNING`
  for longer than 20 minutes
- **THEN** the script SHALL exit non-zero with a diagnostic
  naming the task ARN and SHALL NOT issue
  `update-service --force-new-deployment`

### Requirement: Forced ECS service redeploy is unconditional

`scripts/deploy.sh` SHALL invoke
`aws ecs update-service --cluster nica-erp-demo --service nica-erp-api --force-new-deployment`
on every successful run, regardless of whether `terraform apply`
reported task-definition changes. The redeploy SHALL be issued
**after** `run-migrations.sh` succeeds and **before**
`deploy-web.sh` runs.

#### Scenario: Redeploy issues even when terraform reports no changes

- **WHEN** `make deploy` is run a second time with no changes since
  the previous successful deploy
- **THEN** the AWS CloudTrail event log SHALL show one
  `UpdateService` API call with `forceNewDeployment=true`
