output "user_pool_id" {
  description = "Cognito User Pool ID."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN."
  value       = aws_cognito_user_pool.this.arn
}

output "user_pool_client_id" {
  description = "Cognito SPA app client ID."
  value       = aws_cognito_user_pool_client.spa.id
}

output "user_pool_domain" {
  description = "Fully-qualified Cognito hosted domain (e.g. nica-erp.auth.us-east-1.amazoncognito.com). No scheme prefix."
  value       = "${aws_cognito_user_pool_domain.this.domain}.auth.us-east-1.amazoncognito.com"
}
