# terraform-state-backend Specification

## Purpose
TBD - created by archiving change add-terraform-state-backend. Update Purpose after archive.
## Requirements
### Requirement: S3 state bucket `nica-erp-tf-state-<account-id>` is the Terraform remote state backend

The bootstrap Terraform root SHALL create an S3 bucket named
`nica-erp-tf-state-${data.aws_caller_identity.current.account_id}`
configured with: versioning **enabled**, server-side encryption with
`aws:kms` using an AWS managed key (`alias/aws/s3`), and
`BlockPublicAccess` with all four flags (`BlockPublicAcls`,
`BlockPublicPolicy`, `IgnorePublicAcls`, `RestrictPublicBuckets`) set to
`true`. The bucket SHALL carry the tag `Project=nica-erp`. The bucket
SHALL deny any request whose `aws:SecureTransport` condition is `false`.

The account-id suffix guarantees global uniqueness across all AWS
accounts. The bucket name is exposed as the `tf_state_bucket` Terraform
output for downstream Terraform roots to consume.

#### Scenario: Versioning protects state from accidental deletion

- **WHEN** an operator runs `make bootstrap` against a clean account
- **THEN** `aws s3api get-bucket-versioning --bucket "$(terraform -chdir=infra/terraform/bootstrap output -raw tf_state_bucket)"`
  SHALL return `Status=Enabled`

#### Scenario: Public access is fully blocked

- **WHEN** `aws s3api get-public-access-block --bucket "$(terraform -chdir=infra/terraform/bootstrap output -raw tf_state_bucket)"`
  is called after bootstrap
- **THEN** all four block flags SHALL be `true`

### Requirement: DynamoDB table `nica-erp-tf-lock` provides Terraform locking

The bootstrap Terraform root SHALL create a DynamoDB table named
`nica-erp-tf-lock` with billing mode `PAY_PER_REQUEST`, hash key
`LockID` of type `String`, and tag `Project=nica-erp`. The table SHALL
be consumable as the `dynamodb_table` argument of an `s3` Terraform
backend. (The lock table name does not carry an account-id suffix
because DynamoDB table names are scoped per-account-per-region, not
globally.)

#### Scenario: Lock table exists with the correct schema

- **WHEN** `aws dynamodb describe-table --table-name nica-erp-tf-lock`
  is called after bootstrap
- **THEN** the response SHALL show `KeySchema[0]={AttributeName: LockID,
  KeyType: HASH}`, `AttributeDefinitions[0].AttributeType=S`, and
  `BillingModeSummary.BillingMode=PAY_PER_REQUEST`

### Requirement: Bootstrap root uses local state, not the bucket it creates

`infra/terraform/bootstrap/` SHALL NOT declare a `backend "s3"` block;
its state SHALL be stored locally at
`infra/terraform/bootstrap/terraform.tfstate` and gitignored alongside
`.terraform/` and `terraform.tfvars`. Every non-bootstrap Terraform root
in this repo SHALL declare an `s3` backend whose `bucket` is the
`tf_state_bucket` output of the bootstrap root,
`dynamodb_table = "nica-erp-tf-lock"`, and `encrypt = true`.

#### Scenario: Bootstrap state is local

- **WHEN** `make bootstrap` finishes successfully
- **THEN** `infra/terraform/bootstrap/terraform.tfstate` SHALL exist on
  the operator host and SHALL NOT be tracked by git

