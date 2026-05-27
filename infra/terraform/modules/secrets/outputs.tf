output "ssm_parameter_arns" {
  description = "Map of logical name → SSM parameter ARN, for the compute module's task definitions and IAM task role."
  value = {
    database_url           = aws_ssm_parameter.rds_url.arn
    alembic_database_url   = aws_ssm_parameter.rds_alembic_url.arn
    rds_username           = aws_ssm_parameter.rds_username.arn
    rds_password           = aws_ssm_parameter.rds_password.arn
    cognito_user_pool_id   = aws_ssm_parameter.cognito_user_pool_id.arn
    cognito_client_id      = aws_ssm_parameter.cognito_client_id.arn
    jwt_secret_placeholder = aws_ssm_parameter.jwt_secret_placeholder.arn
  }
}
