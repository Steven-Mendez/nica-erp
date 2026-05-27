data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Bootstrap outputs consumed by this env. The bootstrap state lives
# under `envs/bootstrap/terraform.tfstate` in the same S3 bucket;
# we read it via a remote_state data source rather than copying
# values into tfvars.
#
# NOTE: the bootstrap currently uses LOCAL state (chicken-and-egg —
# it can't store its own creation). Until that changes, this env
# reads bootstrap outputs via direct AWS data sources (ECR repo
# describe + CloudFront distribution describe by tag).

data "aws_ecr_repository" "api" {
  name = "nica-erp"
}

# The bootstrap CloudFront distribution is identified by the Project
# tag. Look it up so we can re-target its /api/* origin at the ALB
# created here.
data "aws_cloudfront_distribution" "bootstrap" {
  # `aws_cloudfront_distribution` is a data source by `id`, not by
  # tag. Pass the ID via tfvars. (Cleaner: have the operator paste
  # the ID once after `make bootstrap`.)
  id = var.cloudfront_distribution_id
}

# The CloudWatch Logs group consumed by ECS task definitions (compute)
# and created by the observability module. Sharing the name via a local
# lets compute be declared before observability — per sprint 01 §Ephemeral
# modules and the change-spec ordering (network → data → auth → secrets →
# compute → observability) — without an `observability → compute → observability`
# cycle in the module graph. Observability still depends on compute for
# the ALB ARN suffix it watches with `nica-erp-alb-5xx`.
locals {
  api_log_group_name = "/nica-erp/api"
}

# ---- Modules ---------------------------------------------------------------

module "network" {
  source = "../../modules/network"
}

module "data" {
  source = "../../modules/data"

  private_subnet_ids = module.network.private_subnet_ids
  sg_rds_id          = module.network.sg_rds_id
}

module "auth" {
  source = "../../modules/auth"

  cognito_domain_prefix = var.cognito_domain_prefix
}

module "secrets" {
  source = "../../modules/secrets"

  rds_endpoint         = module.data.rds_endpoint
  rds_port             = module.data.rds_port
  rds_username         = module.data.rds_username
  rds_password         = module.data.rds_password
  rds_database_name    = module.data.rds_database_name
  cognito_user_pool_id = module.auth.user_pool_id
  cognito_client_id    = module.auth.user_pool_client_id
}

module "compute" {
  source = "../../modules/compute"

  aws_region         = data.aws_region.current.name
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids
  sg_alb_id          = module.network.sg_alb_id
  sg_ecs_tasks_id    = module.network.sg_ecs_tasks_id
  ecr_repository_url = data.aws_ecr_repository.api.repository_url
  image_tag          = var.image_tag
  ssm_parameter_arns = module.secrets.ssm_parameter_arns
  log_group_name     = local.api_log_group_name
  api_min_capacity   = var.api_min_capacity
  api_max_capacity   = var.api_max_capacity
}

module "observability" {
  source = "../../modules/observability"

  alert_email     = var.alert_email
  log_group_name  = local.api_log_group_name
  alb_arn_suffix  = module.compute.alb_arn_suffix
  rds_instance_id = module.data.rds_instance_id
}
