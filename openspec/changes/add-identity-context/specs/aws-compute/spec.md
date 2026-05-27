## MODIFIED Requirements

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
  `COGNITO_CLIENT_ID` ← SSM `/nica-erp/demo/cognito/client-id`,
  `SES_FROM_ADDRESS` ← SSM `/nica-erp/demo/ses/from-address`.
- `logConfiguration`: `awslogs` driver streaming to log group
  `/nica-erp/api`, region `us-east-1`, stream-prefix `api`.

The task role SHALL grant `ssm:GetParameters` on the SSM ARNs
listed above (including the new `/nica-erp/demo/ses/from-address`
parameter) and `kms:Decrypt` on `alias/aws/ssm`. The execution
role SHALL include the AWS managed policies
`AmazonECSTaskExecutionRolePolicy` and grant `ecr:GetAuthorizationToken`,
`ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`,
`ecr:GetDownloadUrlForLayer` on the `nica-erp` ECR ARN.

#### Scenario: Secrets are referenced, not inlined

- **WHEN** the JSON of the `api` container definition is inspected
- **THEN** the `secrets[*].valueFrom` array SHALL include the five
  SSM parameter ARNs listed above, and the `environment[*].value`
  array SHALL NOT contain any database password, Cognito secret, or
  SES sender literal

#### Scenario: `SES_FROM_ADDRESS` is projected from SSM

- **WHEN** the JSON of the `api` container definition is inspected
- **THEN** the `secrets[*]` array SHALL include exactly one entry
  whose `name` is `SES_FROM_ADDRESS` and whose `valueFrom` points at
  the SSM parameter ARN for `/nica-erp/demo/ses/from-address`

#### Scenario: Task role can read the SES parameter

- **WHEN** `aws iam get-role-policy --role-name <api-task-role>` is
  invoked after apply
- **THEN** the policy's `Statement[*].Resource` array SHALL include
  the SSM parameter ARN for `/nica-erp/demo/ses/from-address` under
  the `ssm:GetParameters` action
