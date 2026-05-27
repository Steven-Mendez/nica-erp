variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = { Project = "nica-erp" }
}

variable "name_prefix" {
  description = "Prefix applied to every Name tag."
  type        = string
  default     = "nica-erp-demo"
}

variable "aws_region" {
  description = "AWS region (used by the awslogs driver)."
  type        = string
}

# ---- Network wiring (from the network module) ------------------------------

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the ALB."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the ECS tasks."
  type        = list(string)
}

variable "sg_alb_id" {
  description = "ALB security group ID."
  type        = string
}

variable "sg_ecs_tasks_id" {
  description = "ECS task security group ID."
  type        = string
}

# ---- Image + secrets wiring ------------------------------------------------

variable "ecr_repository_url" {
  description = "ECR repository URL (e.g. <account>.dkr.ecr.<region>.amazonaws.com/nica-erp)."
  type        = string
}

variable "image_tag" {
  description = "Image tag pulled by both task definitions. Same tag for API and migrate."
  type        = string
}

variable "ssm_parameter_arns" {
  description = "Map of logical name → SSM SecureString ARN consumed by the task definitions."
  type        = map(string)
}

variable "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN. Used to scope the cognito-idp IAM allow-list on the API Fargate task role."
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch Logs group consumed by the awslogs driver."
  type        = string
  default     = "/nica-erp/api"
}

# ---- Task sizing -----------------------------------------------------------

variable "api_cpu" {
  description = "Fargate CPU units for the API task."
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Fargate memory (MiB) for the API task."
  type        = number
  default     = 512
}

variable "api_min_capacity" {
  description = "Minimum desired count for the API service (MVP default = 1)."
  type        = number
  default     = 1
}

variable "api_max_capacity" {
  description = "Maximum desired count for the API service. Set equal to min for no autoscaling at MVP default."
  type        = number
  default     = 1
}
