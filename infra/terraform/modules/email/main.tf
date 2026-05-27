# SES email-identity for the operator sender. The MVP runs in the
# permanent SES sandbox (≤ 50 verified recipients, 200 mails/24h) and
# uses a single email-identity — NO domain identity, NO MAIL FROM
# domain, NO DKIM/SPF, NO Route53. See ADR-0020.
#
# After apply, AWS sends a verification email to var.from_address.
# The operator MUST click the link before the first signup; Terraform
# cannot click links. The `verification_reminder` output surfaces this
# instruction in the apply output.

resource "aws_sesv2_email_identity" "sender" {
  email_identity = var.from_address

  tags = merge(var.tags, { Project = "nica-erp" })
}
