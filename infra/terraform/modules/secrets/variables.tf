variable "tags" {
  description = "Tags applied to every SSM parameter."
  type        = map(string)
  default     = { Project = "nica-erp" }
}

variable "ssm_prefix" {
  description = "Path prefix under SSM Parameter Store for the demo env."
  type        = string
  default     = "/nica-erp/demo"
}

variable "rds_endpoint" {
  description = "RDS hostname."
  type        = string
}

variable "rds_port" {
  description = "RDS port."
  type        = number
}

variable "rds_username" {
  description = "RDS master username."
  type        = string
  sensitive   = true
}

variable "rds_password" {
  description = "RDS master password."
  type        = string
  sensitive   = true
}

variable "rds_database_name" {
  description = "RDS initial database name."
  type        = string
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID."
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito SPA app client ID."
  type        = string
}

variable "cognito_user_pool_domain" {
  description = "Fully-qualified Cognito hosted domain (e.g. nica-erp.auth.us-east-1.amazoncognito.com). Public; stored as plain `String`."
  type        = string
}

variable "from_address" {
  description = "Operator's email address used as the SES sender identity. Plumbed in from module.email."
  type        = string
}
