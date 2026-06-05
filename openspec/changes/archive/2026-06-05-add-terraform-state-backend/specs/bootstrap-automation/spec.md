## ADDED Requirements

### Requirement: `make bootstrap` provisions persistent AWS resources idempotently

The root `Makefile` SHALL declare a target `bootstrap` that delegates
to `scripts/bootstrap.sh`. The script SHALL run
`terraform -chdir=infra/terraform/bootstrap init` followed by
`terraform -chdir=infra/terraform/bootstrap apply -auto-approve` and
SHALL print the following Terraform outputs to stdout on success:
`cloudfront_distribution_domain`, `tf_state_bucket`,
`ecr_repository_url`, `web_bucket`. A second invocation against an
already-bootstrapped account SHALL exit `0` and the underlying
`terraform plan` SHALL report `No changes`.

#### Scenario: First-time bootstrap prints the public URL

- **WHEN** `make bootstrap` runs against an account with no
  nica-erp resources
- **THEN** the script SHALL exit `0` and stdout SHALL contain a line
  matching `^cloudfront_distribution_domain = .*\.cloudfront\.net$`

#### Scenario: Repeated bootstrap is a no-op

- **WHEN** `make bootstrap` is run a second time within five minutes
  of the first
- **THEN** the underlying `terraform plan` invoked by the script
  SHALL report `No changes` and the script SHALL exit `0`

### Requirement: `make destroy-bootstrap` requires explicit operator confirmation

The root `Makefile` SHALL declare a target `destroy-bootstrap` that
delegates to `scripts/destroy-bootstrap.sh`. The script SHALL prompt
the operator with the message
`Type 'nica-erp-bootstrap' to confirm destruction:` and SHALL exit
non-zero without performing any destructive action if the read input
does not match exactly. On confirmation, the script SHALL: (1) delete
every object and version in the state bucket and the SPA bucket
(`tf_state_bucket` / `web_bucket` outputs), (2) delete every image in
the ECR repository `nica-erp`, (3) run
`terraform -chdir=infra/terraform/bootstrap destroy -auto-approve`.

#### Scenario: Wrong confirmation string aborts safely

- **WHEN** the operator runs `make destroy-bootstrap` and types
  anything other than `nica-erp-bootstrap`
- **THEN** the script SHALL exit non-zero, no AWS API calls that
  delete data SHALL have been issued, and the bootstrap resources
  SHALL remain intact

#### Scenario: Correct confirmation empties buckets and ECR before destroy

- **WHEN** the operator types `nica-erp-bootstrap` and the ephemeral
  stack is absent
- **THEN** the script SHALL invoke (in order) bucket emptying for
  the state bucket and the SPA bucket, image deletion for ECR
  `nica-erp`, and `terraform destroy -auto-approve`, and SHALL exit
  `0`

### Requirement: `destroy-bootstrap` refuses to run while ephemeral resources are alive

Before performing any deletion, `scripts/destroy-bootstrap.sh` SHALL
query the AWS Resource Groups Tagging API for resources with
`Project=nica-erp` and SHALL exit non-zero with a diagnostic message
if any resource is found whose type is not one of: `s3:bucket`
(matching `nica-erp-tf-state-<account-id>` or
`nica-erp-web-<account-id>`), `dynamodb:table` (matching
`nica-erp-tf-lock`), `ecr:repository` (matching `nica-erp`), or
`cloudfront:distribution` (matching the bootstrap-created distribution).

#### Scenario: Ephemeral VPC or RDS blocks bootstrap destruction

- **WHEN** the operator runs `make destroy-bootstrap` while a VPC
  tagged `Project=nica-erp` is still alive in the account
- **THEN** the script SHALL exit non-zero and print a message naming
  the offending resource type and ARN, and SHALL NOT empty any
  bucket or invoke `terraform destroy`

### Requirement: Bootstrap scripts pin the AWS profile and region

`scripts/bootstrap.sh` and `scripts/destroy-bootstrap.sh` SHALL export
`AWS_PROFILE=nica-erp`, `AWS_REGION=us-east-1`, and
`AWS_DEFAULT_REGION=us-east-1` before invoking any AWS CLI or
Terraform command. The `aws` provider in
`infra/terraform/bootstrap/providers.tf` SHALL set
`profile = var.aws_profile`, with the variable defaulted to
`"nica-erp"`. The AWS CLI default profile and any region other than
`us-east-1` SHALL NOT be used by either script.

#### Scenario: Bootstrap fails fast when the `nica-erp` profile is unconfigured

- **WHEN** an operator runs `make bootstrap` on a host where the
  `nica-erp` profile is not present in `~/.aws/credentials` or
  `~/.aws/config`
- **THEN** the script SHALL exit non-zero with a diagnostic that names
  the missing profile, and SHALL NOT invoke `terraform apply`

### Requirement: Bootstrap script runs an IAM permissions canary

`scripts/bootstrap.sh` SHALL execute, before any `terraform init` or
`terraform apply` invocation, one cheap read-only AWS API call per
service it depends on: `s3api list-buckets`, `dynamodb list-tables`,
`ecr describe-repositories`, and `cloudfront list-distributions`. If
any call fails for any reason, the script SHALL exit non-zero with a
diagnostic that names the failing call and the IAM actions required
by the bootstrap, and SHALL NOT invoke `terraform apply`.

#### Scenario: Missing permission aborts before terraform apply

- **WHEN** the `nica-erp` profile lacks `cloudfront:ListDistributions`
- **THEN** `make bootstrap` SHALL exit non-zero with a message naming
  the failing call, and `terraform apply` SHALL NOT have been invoked

### Requirement: Bootstrap Terraform root carries `Project=nica-erp` on every resource

Every taggable resource created by the bootstrap Terraform root SHALL
declare an explicit `tags = { Project = "nica-erp" }` block. The
`aws` provider SHALL NOT use `default_tags` (to keep `terraform plan`
free of the well-known first-plan diff that default_tags produces on
S3 and ECR).

#### Scenario: Resource Groups Tagging API surfaces every bootstrap resource

- **WHEN** the operator runs
  `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`
  after `make bootstrap`
- **THEN** the response SHALL include the ARNs of the state bucket
  (`nica-erp-tf-state-<account-id>`), the lock table
  (`nica-erp-tf-lock`), the ECR repository (`nica-erp`), the SPA
  bucket (`nica-erp-web-<account-id>`), and the CloudFront
  distribution

### Requirement: Bucket names are suffixed with the AWS account id

The state bucket and the SPA bucket SHALL be named
`nica-erp-tf-state-${data.aws_caller_identity.current.account_id}`
and `nica-erp-web-${data.aws_caller_identity.current.account_id}`
respectively. The account id SHALL be obtained via
`data "aws_caller_identity" "current"` and exposed as the
`aws_account_id` Terraform output. The bucket names themselves SHALL
be exposed as `tf_state_bucket` and `web_bucket` outputs so consumers
do not have to recompute them.

#### Scenario: First bootstrap against account 123456789012 produces deterministic bucket names

- **WHEN** `make bootstrap` runs in an account whose id is
  `123456789012`
- **THEN** `terraform -chdir=infra/terraform/bootstrap output -raw tf_state_bucket`
  SHALL print `nica-erp-tf-state-123456789012` and
  `terraform -chdir=infra/terraform/bootstrap output -raw web_bucket`
  SHALL print `nica-erp-web-123456789012`
