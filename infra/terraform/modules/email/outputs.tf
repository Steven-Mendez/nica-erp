output "from_address" {
  description = "The SES-registered sender address (equal to var.from_address)."
  value       = aws_sesv2_email_identity.sender.email_identity
}

output "verification_reminder" {
  description = "Human-readable reminder that the operator must click the SES verification link before the first signup."
  value       = "Operator: verify the SES sender '${var.from_address}' in the AWS console (us-east-1) before the first signup. Terraform cannot click the verification link."
}
