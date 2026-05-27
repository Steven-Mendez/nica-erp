locals {
  image_uri = "${var.ecr_repository_url}:${var.image_tag}"

  # Shared `secrets` block: the value AWS injects into the container
  # is the *decrypted* SSM parameter content (not the ARN). The map
  # is keyed by env-var name, valued by parameter ARN.
  container_secrets = [
    {
      name      = "DATABASE_URL"
      valueFrom = var.ssm_parameter_arns["database_url"]
    },
    {
      name      = "ALEMBIC_DATABASE_URL"
      valueFrom = var.ssm_parameter_arns["alembic_database_url"]
    },
    {
      name      = "COGNITO_USER_POOL_ID"
      valueFrom = var.ssm_parameter_arns["cognito_user_pool_id"]
    },
    {
      name      = "COGNITO_CLIENT_ID"
      valueFrom = var.ssm_parameter_arns["cognito_client_id"]
    },
  ]

  container_environment = [
    { name = "APP_ENV", value = "aws" },
  ]

  log_configuration = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = var.log_group_name
      awslogs-region        = var.aws_region
      awslogs-stream-prefix = "api"
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name             = "api"
      image            = local.image_uri
      essential        = true
      portMappings     = [{ containerPort = 8000, protocol = "tcp" }]
      environment      = local.container_environment
      secrets          = local.container_secrets
      logConfiguration = local.log_configuration
    }
  ])

  tags = merge(var.tags, { Name = "${var.name_prefix}-api" })
}

# Migration task — same container image, same env, but the command
# overrides uvicorn with `alembic upgrade head`. Invoked by
# scripts/run-migrations.sh via ECS RunTask.
resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name_prefix}-migrate"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name             = "migrate"
      image            = local.image_uri
      essential        = true
      command          = ["alembic", "upgrade", "head"]
      environment      = local.container_environment
      secrets          = local.container_secrets
      logConfiguration = local.log_configuration
    }
  ])

  tags = merge(var.tags, { Name = "${var.name_prefix}-migrate" })
}
