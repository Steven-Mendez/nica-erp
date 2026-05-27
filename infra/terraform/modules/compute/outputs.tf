output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.api.name
}

output "api_task_definition_arn" {
  description = "ARN of the API task definition (current revision)."
  value       = aws_ecs_task_definition.api.arn
}

output "migrate_task_definition_arn" {
  description = "ARN of the migration task definition (current revision)."
  value       = aws_ecs_task_definition.migrate.arn
}

output "alb_arn" {
  description = "ALB ARN."
  value       = aws_lb.this.arn
}

output "alb_arn_suffix" {
  description = "ALB ARN suffix used by CloudWatch metric dimensions."
  value       = aws_lb.this.arn_suffix
}

output "alb_dns_name" {
  description = "ALB DNS name — fed into CloudFront /api/* origin."
  value       = aws_lb.this.dns_name
}

output "target_group_arn" {
  description = "API target group ARN."
  value       = aws_lb_target_group.api.arn
}

output "task_subnets" {
  description = "Private subnets where ECS tasks run; consumed by ECS RunTask in the migration script."
  value       = var.private_subnet_ids
}

output "task_security_group_id" {
  description = "Security group ID attached to ECS tasks."
  value       = var.sg_ecs_tasks_id
}
