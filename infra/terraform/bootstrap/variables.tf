variable "aws_region" {
  description = "AWS region for all bootstrap resources. CloudFront is global but the API/S3/ECR resources live in this region."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Named AWS CLI profile used for the bootstrap apply. Required: the project must not run against the default profile."
  type        = string
  default     = "nica-erp"
}
