## ADDED Requirements

### Requirement: SES email identity for the operator sender

The `infra/terraform/modules/email/` module SHALL declare one
`aws_sesv2_email_identity` whose `email_identity` is the variable
`from_address` (the operator's address). The resource SHALL be created
in `us-east-1`. The module SHALL output `from_address` for downstream
modules (`secrets`). The module MUST NOT declare a domain identity, a
`MAIL FROM` domain, an `aws_route53_record`, or any DKIM resource —
the MVP has no controlled DNS zone
([ADR-0020](../../../../docs/adr/0020-no-custom-domain-mvp.md)).

#### Scenario: Email identity exists after apply

- **WHEN** `aws sesv2 list-email-identities --region us-east-1` is
  invoked after `terraform apply`
- **THEN** the response SHALL include an entry whose `IdentityName`
  equals `var.from_address`

#### Scenario: No domain identity is created

- **WHEN** the Terraform plan for `module.email` is inspected
- **THEN** the plan SHALL NOT include any
  `aws_sesv2_email_identity` resource whose `email_identity` looks
  like a bare domain (no `@`)

### Requirement: Permanent SES sandbox

The module SHALL NOT request, automate, or document any procedure for
exiting the SES sandbox. The deployment SHALL operate within the
sandbox constraints (≤ 50 verified recipient addresses, 200 mails /
24 h). Operator runbooks SHALL state that exiting the sandbox is
post-MVP work and is meaningful only with a custom domain.

#### Scenario: Apply does not raise a service limit request

- **WHEN** the Terraform plan for `module.email` is inspected
- **THEN** the plan SHALL NOT include any
  `aws_servicequotas_service_quota` resource targeting the SES
  service

### Requirement: Operator verification ritual

The module SHALL document — in its `README.md` and in the output of
`terraform apply` (via a `null_resource` / `local-exec` echo, or via
a `terraform output` post-apply note) — that **the operator must click
the SES verification link in the AWS-sent email** before the first
signup. Terraform cannot click links; this is operator action, not
infra automation.

#### Scenario: Apply output mentions the verification step

- **WHEN** `terraform apply` succeeds for `module.email`
- **THEN** the apply output SHALL include a human-readable line
  pointing the operator at the SES verification email (exact wording
  is not constrained; the substring "verify" SHALL appear)

### Requirement: Identity is tagged for cost attribution

The `aws_sesv2_email_identity` SHALL carry `Tags = { Project =
"nica-erp" }` so cost-explorer reports can isolate the identity's
sending bill.

#### Scenario: Tag is present on the identity

- **WHEN** `aws sesv2 get-email-identity --email-identity <addr>` is
  called after apply
- **THEN** the response's `Tags` SHALL include `{"Key":"Project",
  "Value":"nica-erp"}`
