output "cloudfront_distribution_id" {
  description = "Bootstrap CloudFront distribution ID (re-exposed for the deploy script)."
  value       = local.cloudfront_distribution_id
}

output "cloudfront_distribution_domain" {
  description = "Bootstrap CloudFront domain name (`<dist>.cloudfront.net`)."
  value       = local.cloudfront_distribution_domain
}

output "alb_dns_name" {
  description = "ALB DNS name — the deploy script swaps the CloudFront /api/* origin to this value."
  value       = module.compute.alb_dns_name
}

output "alb_arn_suffix" {
  description = "ALB ARN suffix (for CloudWatch metric dimensions, if needed externally)."
  value       = module.compute.alb_arn_suffix
}

output "cluster_name" {
  description = "ECS cluster name (consumed by the migration script + force-new-deployment step)."
  value       = module.compute.cluster_name
}

output "service_name" {
  description = "ECS service name."
  value       = module.compute.service_name
}

output "api_task_definition_arn" {
  description = "API task definition ARN (current revision)."
  value       = module.compute.api_task_definition_arn
}

output "migrate_task_definition_arn" {
  description = "Migration task definition ARN (consumed by scripts/run-migrations.sh)."
  value       = module.compute.migrate_task_definition_arn
}

output "target_group_arn" {
  description = "ALB target group ARN."
  value       = module.compute.target_group_arn
}

output "task_subnets" {
  description = "Private subnets where ECS tasks (including the migration RunTask) run."
  value       = module.compute.task_subnets
}

output "task_security_group_id" {
  description = "Security group ID for ECS tasks."
  value       = module.compute.task_security_group_id
}

output "rds_endpoint" {
  description = "RDS hostname."
  value       = module.data.rds_endpoint
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID."
  value       = module.auth.user_pool_id
}

output "cognito_user_pool_client_id" {
  description = "Cognito SPA app client ID."
  value       = module.auth.user_pool_client_id
}

output "log_group_name" {
  description = "CloudWatch Logs group name for the API."
  value       = module.observability.log_group_name
}

output "sns_alerts_topic_arn" {
  description = "SNS topic ARN for ops alerts."
  value       = module.observability.sns_alerts_topic_arn
}

output "ses_verification_reminder" {
  description = "Human-readable reminder that the operator must click the SES verification link before the first signup. Surfaced by `make deploy`."
  value       = module.email.verification_reminder
}
