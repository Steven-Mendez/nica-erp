## ADDED Requirements

### Requirement: `envs/demo` composes the `email/` module

`infra/terraform/envs/demo/main.tf` SHALL declare a `module "email"`
block sourcing `../../modules/email`, passing `from_address =
var.from_address` (a new root variable in
`envs/demo/variables.tf`). The output `module.email.from_address`
SHALL be passed into `module "secrets"` and `module "compute"` so the
API task definition can mount the SES sender as a container env var.

#### Scenario: Demo env declares the email module

- **WHEN** `terraform state list` is run in `envs/demo` after apply
- **THEN** the listing SHALL include
  `module.email.aws_sesv2_email_identity.sender`

### Requirement: `terraform.tfvars.example` documents `from_address`

`envs/demo/terraform.tfvars.example` SHALL include a commented entry
for `from_address` with guidance pointing at the SES verification
step. The real `terraform.tfvars` SHALL remain gitignored.

#### Scenario: Example file mentions `from_address`

- **WHEN** `envs/demo/terraform.tfvars.example` is read
- **THEN** the file SHALL contain a line whose key is `from_address`
  (commented or otherwise)

### Requirement: Apply prints the SES verification reminder

The `envs/demo` root SHALL emit a Terraform output named
`ses_verification_reminder` whose value is a human-readable string
instructing the operator to verify the SES sender in the AWS console
before the first signup. `make deploy` SHALL surface this output to
the operator after the apply.

#### Scenario: Reminder output exists

- **WHEN** `terraform output ses_verification_reminder` is invoked
  after apply
- **THEN** the output SHALL include the substring "verify" and the
  value of `from_address`
