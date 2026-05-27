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

variable "log_group_name" {
  description = "CloudWatch Logs group name for the API."
  type        = string
  default     = "/nica-erp/api"
}

variable "log_retention_days" {
  description = "Retention for the API log group."
  type        = number
  default     = 14
}

variable "alert_email" {
  description = "Email subscribed to the alerts SNS topic."
  type        = string
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix (the portion after `loadbalancer/`) used by the 5xx alarm dimension."
  type        = string
}

variable "rds_instance_id" {
  description = "RDS instance identifier used by the CPU alarm dimension."
  type        = string
}
