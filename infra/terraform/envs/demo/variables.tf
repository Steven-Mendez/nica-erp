variable "aws_region" {
  description = "AWS region for the demo ephemeral stack."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Named AWS CLI profile used by Terraform. Skip in CI (OIDC sets AWS_ACCESS_KEY_ID env instead)."
  type        = string
  default     = null
}

variable "alert_email" {
  description = "Email subscribed to the alerts SNS topic."
  type        = string
}

variable "image_tag" {
  description = "ECR image tag (short SHA) used by both task definitions. Must already be pushed."
  type        = string
}

variable "api_min_capacity" {
  description = "Minimum desired count for the API service."
  type        = number
  default     = 1
}

variable "api_max_capacity" {
  description = "Maximum desired count for the API service. Equal to min at MVP defaults."
  type        = number
  default     = 1
}

variable "cognito_domain_prefix" {
  description = "Cognito hosted-domain prefix."
  type        = string
  default     = "nica-erp"
}

variable "cloudfront_distribution_id" {
  description = "ID of the bootstrap-created CloudFront distribution. Read from `terraform -chdir=infra/terraform/bootstrap output -raw cloudfront_distribution_id` after `make bootstrap`."
  type        = string
}
