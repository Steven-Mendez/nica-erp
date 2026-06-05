# aws-compute Specification

## Purpose
TBD - created by archiving change add-aws-runtime-stack. Update Purpose after archive.
## Requirements
### Requirement: ECS cluster runs Fargate tasks only

The `infra/terraform/modules/compute/` module SHALL create one
`aws_ecs_cluster` named `nica-erp-demo` with
`capacity_providers=["FARGATE"]` and
`setting { name="containerInsights"; value="disabled" }`. The
cluster SHALL carry the tag `Project=nica-erp`.

#### Scenario: Cluster is Fargate-only

- **WHEN** `aws ecs describe-clusters --clusters nica-erp-demo`
  is called after apply
- **THEN** the response SHALL show `capacityProviders=["FARGATE"]`

### Requirement: API task definition wires SSM secrets and CloudWatch logs

The module SHALL create one `aws_ecs_task_definition`
`nica-erp-api` with `requires_compatibilities=["FARGATE"]`,
`network_mode="awsvpc"`, `cpu="256"`, `memory="512"`, one container
named `api` whose `image` is the variable `image_tag` resolved
against `var.ecr_repository_url`, port mapping `containerPort=8000`,
`essential=true`. The container SHALL declare:

- `environment`: `APP_ENV=aws`.
- `secrets`: `DATABASE_URL` ← SSM `/nica-erp/demo/rds/url`,
  `ALEMBIC_DATABASE_URL` ← SSM `/nica-erp/demo/rds/url`,
  `COGNITO_USER_POOL_ID` ← SSM `/nica-erp/demo/cognito/user-pool-id`,
  `COGNITO_CLIENT_ID` ← SSM `/nica-erp/demo/cognito/client-id`.
- `logConfiguration`: `awslogs` driver streaming to log group
  `/nica-erp/api`, region `us-east-1`, stream-prefix `api`.

The task role SHALL grant `ssm:GetParameters` on the SSM ARNs
listed above and `kms:Decrypt` on `alias/aws/ssm`. The execution
role SHALL include the AWS managed policies
`AmazonECSTaskExecutionRolePolicy` and grant `ecr:GetAuthorizationToken`,
`ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`,
`ecr:GetDownloadUrlForLayer` on the `nica-erp` ECR ARN.

#### Scenario: Secrets are referenced, not inlined

- **WHEN** the JSON of the `api` container definition is inspected
- **THEN** the `secrets[*].valueFrom` array SHALL include the four
  SSM parameter ARNs listed above, and the `environment[*].value`
  array SHALL NOT contain any database password or Cognito secret
  literal

### Requirement: Migration task definition shares the API image but overrides command

The module SHALL create a second `aws_ecs_task_definition`
`nica-erp-migrate` with the same `image`, environment, secrets, and
log configuration as `nica-erp-api`, but whose container
`command` overrides to `["alembic","upgrade","head"]`. The task
SHALL NOT be attached to any ECS service; it SHALL be invoked only
via `aws ecs run-task` from the migration script
(in `add-deploy-destroy-automation`).

#### Scenario: Migration task command override

- **WHEN** the JSON of the migration task definition is inspected
- **THEN** `containerDefinitions[0].command` SHALL equal
  `["alembic","upgrade","head"]` and the image SHALL match the
  image of `nica-erp-api`

### Requirement: ECS service runs the API behind the ALB target group

The module SHALL create one `aws_ecs_service` `nica-erp-api`
referencing the API task definition with `desired_count=1`,
`launch_type="FARGATE"`,
`deployment_minimum_healthy_percent=100`,
`deployment_maximum_percent=200`, attached to the private subnets
and the `sg_ecs_tasks` security group. The service SHALL attach to
the ALB target group via `load_balancer { target_group_arn=<tg>; container_name="api"; container_port=8000 }`.

#### Scenario: Service desired count and capacity

- **WHEN** `aws ecs describe-services --cluster nica-erp-demo --services nica-erp-api`
  is called after apply
- **THEN** the response SHALL show `desiredCount=1`,
  `runningCount=1`, `launchType=FARGATE`, and exactly one
  `loadBalancers` entry

### Requirement: ALB on HTTP :80, no HTTPS listener

The module SHALL create one `aws_lb` named `nica-erp-demo-alb`,
internet-facing, attached to the public subnets and the `sg_alb`
security group, with one `aws_lb_listener` on `protocol="HTTP"`,
`port=80`, `default_action.type="forward"` to a target group whose
`protocol="HTTP"`, `port=8000`, `target_type="ip"`, health check
path `/api/healthz`, healthy threshold `2`, unhealthy threshold
`3`, interval `15s`, timeout `5s`, matcher `200`. The module SHALL
NOT create any HTTPS listener or attach any ACM certificate.

#### Scenario: No HTTPS listener exists

- **WHEN** `aws elbv2 describe-listeners --load-balancer-arn <alb>`
  is called after apply
- **THEN** the response SHALL list exactly one listener with
  `Protocol=HTTP, Port=80`

#### Scenario: Target group health check hits /api/healthz

- **WHEN** the target group attributes are inspected
- **THEN** `HealthCheckPath` SHALL be `/api/healthz` and `Matcher`
  SHALL be `200`

### Requirement: Auto-scaling policy declared but inactive at default capacity

The module SHALL create `aws_appautoscaling_target` and
`aws_appautoscaling_policy` resources for the API service with:
`min_capacity=var.api_min_capacity`,
`max_capacity=var.api_max_capacity`, policy type
`TargetTrackingScaling`,
`predefined_metric_specification.predefined_metric_type=ECSServiceAverageCPUUtilization`,
`target_value=50`, `scale_in_cooldown=300`, `scale_out_cooldown=60`.
Default variable values SHALL be `api_min_capacity=1`,
`api_max_capacity=1`. Raising `api_max_capacity` SHALL activate the
policy without requiring a re-declaration of the policy resource
(`terraform plan` SHALL show only target-capacity changes).

#### Scenario: Default capacity is pinned to one

- **WHEN** the appautoscaling target is inspected with default
  module inputs
- **THEN** `MinCapacity` SHALL equal `1` and `MaxCapacity` SHALL
  equal `1`

#### Scenario: Raising max capacity does not recreate the policy

- **WHEN** `api_max_capacity=3` is set and
  `terraform plan` is run
- **THEN** the plan SHALL show only changes to
  `aws_appautoscaling_target.api.max_capacity` and SHALL NOT
  recreate `aws_appautoscaling_policy.api`

