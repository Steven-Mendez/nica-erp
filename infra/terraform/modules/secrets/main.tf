locals {
  database_url = format(
    "postgresql+asyncpg://%s:%s@%s:%d/%s",
    var.rds_username,
    var.rds_password,
    var.rds_endpoint,
    var.rds_port,
    var.rds_database_name,
  )

  alembic_database_url = format(
    "postgresql+psycopg://%s:%s@%s:%d/%s",
    var.rds_username,
    var.rds_password,
    var.rds_endpoint,
    var.rds_port,
    var.rds_database_name,
  )
}

resource "aws_ssm_parameter" "rds_url" {
  name        = "${var.ssm_prefix}/rds/url"
  description = "DATABASE_URL (asyncpg) consumed by the API container."
  type        = "SecureString"
  value       = local.database_url
  key_id      = "alias/aws/ssm"

  tags = var.tags
}

resource "aws_ssm_parameter" "rds_alembic_url" {
  name        = "${var.ssm_prefix}/rds/alembic_url"
  description = "ALEMBIC_DATABASE_URL (psycopg sync) for the migration RunTask."
  type        = "SecureString"
  value       = local.alembic_database_url
  key_id      = "alias/aws/ssm"

  tags = var.tags
}

resource "aws_ssm_parameter" "rds_username" {
  name        = "${var.ssm_prefix}/rds/username"
  description = "RDS master username."
  type        = "SecureString"
  value       = var.rds_username
  key_id      = "alias/aws/ssm"

  tags = var.tags
}

resource "aws_ssm_parameter" "rds_password" {
  name        = "${var.ssm_prefix}/rds/password"
  description = "RDS master password."
  type        = "SecureString"
  value       = var.rds_password
  key_id      = "alias/aws/ssm"

  tags = var.tags
}

resource "aws_ssm_parameter" "cognito_user_pool_id" {
  name        = "${var.ssm_prefix}/cognito/user-pool-id"
  description = "Cognito User Pool ID for the API to validate JWTs."
  type        = "SecureString"
  value       = var.cognito_user_pool_id
  key_id      = "alias/aws/ssm"

  tags = var.tags
}

resource "aws_ssm_parameter" "cognito_client_id" {
  name        = "${var.ssm_prefix}/cognito/client-id"
  description = "Cognito SPA app client ID."
  type        = "SecureString"
  value       = var.cognito_client_id
  key_id      = "alias/aws/ssm"

  tags = var.tags
}

# Placeholder, intentionally empty. AWS does not use LOCAL_JWT_SECRET —
# Cognito-issued JWTs replace it. Sprint 02 fills it in if/when needed.
resource "aws_ssm_parameter" "jwt_secret_placeholder" {
  name        = "${var.ssm_prefix}/jwt/secret"
  description = "Placeholder. AWS uses Cognito JWTs; this parameter exists so later sprints can populate it without restructuring SSM."
  type        = "SecureString"
  value       = " "
  key_id      = "alias/aws/ssm"

  lifecycle {
    ignore_changes = [value]
  }

  tags = var.tags
}
