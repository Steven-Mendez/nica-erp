output "aws_account_id" {
  description = "AWS account id the bootstrap was applied to. Bucket names suffix this value."
  value       = local.account_id
}

output "tf_state_bucket" {
  description = "S3 bucket holding remote Terraform state for non-bootstrap roots."
  value       = aws_s3_bucket.tf_state.bucket
}

output "tf_state_bucket_arn" {
  description = "ARN of the remote Terraform state bucket."
  value       = aws_s3_bucket.tf_state.arn
}

output "tf_lock_table" {
  description = "DynamoDB table used as the Terraform state lock."
  value       = aws_dynamodb_table.tf_lock.name
}

output "tf_lock_table_arn" {
  description = "ARN of the Terraform state lock table."
  value       = aws_dynamodb_table.tf_lock.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL that holds API container images."
  value       = aws_ecr_repository.api.repository_url
}

output "web_bucket" {
  description = "S3 bucket that holds the built SPA."
  value       = aws_s3_bucket.web.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID fronting the SPA and the future /api/* origin."
  value       = aws_cloudfront_distribution.web.id
}

output "cloudfront_distribution_arn" {
  description = "CloudFront distribution ARN."
  value       = aws_cloudfront_distribution.web.arn
}

output "cloudfront_distribution_domain" {
  description = "Public CloudFront domain name (default *.cloudfront.net cert)."
  value       = aws_cloudfront_distribution.web.domain_name
}
