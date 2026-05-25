## ADDED Requirements

### Requirement: `make bootstrap` provisions persistent AWS resources idempotently

The root `Makefile` SHALL declare a target `bootstrap` that delegates
to `scripts/bootstrap.sh`. The script SHALL run
`terraform -chdir=infra/terraform/bootstrap init` followed by
`terraform -chdir=infra/terraform/bootstrap apply -auto-approve` and
SHALL print the following Terraform outputs to stdout on success:
`cloudfront_distribution_domain`,
`tf_state_bucket`, `ecr_repository_url`, `web_bucket`. A second
invocation against an already-bootstrapped account SHALL exit `0` and
the underlying `terraform plan` SHALL report `No changes` (caveats:
`default_tags` and S3 ETags noted in the design).

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
every object and version in `nica-erp-tf-state` and `nica-erp-web`,
(2) delete every image in the ECR repository `nica-erp`, (3) run
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
  `nica-erp-tf-state` and `nica-erp-web`, image deletion for ECR
  `nica-erp`, and `terraform destroy -auto-approve`, and SHALL exit
  `0`

### Requirement: `destroy-bootstrap` refuses to run while ephemeral resources are alive

Before performing any deletion, `scripts/destroy-bootstrap.sh` SHALL
query the AWS Resource Groups Tagging API for resources with
`Project=nica-erp` and SHALL exit non-zero with a diagnostic message
if any resource is found whose type is not one of: `s3:bucket`
(matching `nica-erp-tf-state` or `nica-erp-web`), `dynamodb:table`
(matching `nica-erp-tf-lock`), `ecr:repository` (matching `nica-erp`),
or `cloudfront:distribution` (matching the bootstrap-created
distribution).

#### Scenario: Ephemeral VPC or RDS blocks bootstrap destruction

- **WHEN** the operator runs `make destroy-bootstrap` while a VPC
  tagged `Project=nica-erp` is still alive in the account
- **THEN** the script SHALL exit non-zero and print a message naming
  the offending resource type and ARN, and SHALL NOT empty any
  bucket or invoke `terraform destroy`

### Requirement: Bootstrap Terraform root carries `Project=nica-erp` on every resource

The `aws` provider in `infra/terraform/bootstrap/` SHALL set
`default_tags = { Project = "nica-erp" }`. Resources whose default-tag
propagation is unreliable (S3 buckets and ECR repositories) SHALL
also declare the tag explicitly in their `tags` block.

#### Scenario: Resource Groups Tagging API surfaces every bootstrap resource

- **WHEN** the operator runs
  `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`
  after `make bootstrap`
- **THEN** the response SHALL include the ARNs of
  `nica-erp-tf-state`, `nica-erp-tf-lock`, `nica-erp` (ECR),
  `nica-erp-web`, and the CloudFront distribution
