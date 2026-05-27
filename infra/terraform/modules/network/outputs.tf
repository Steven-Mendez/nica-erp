output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "VPC CIDR block."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "List of public subnet IDs (one per AZ, deterministic order)."
  value       = [for k in sort(keys(aws_subnet.public)) : aws_subnet.public[k].id]
}

output "private_subnet_ids" {
  description = "List of private subnet IDs (one per AZ, deterministic order)."
  value       = [for k in sort(keys(aws_subnet.private)) : aws_subnet.private[k].id]
}

output "sg_alb_id" {
  description = "ALB security group ID."
  value       = aws_security_group.alb.id
}

output "sg_ecs_tasks_id" {
  description = "ECS task security group ID."
  value       = aws_security_group.ecs_tasks.id
}

output "sg_rds_id" {
  description = "RDS security group ID."
  value       = aws_security_group.rds.id
}
