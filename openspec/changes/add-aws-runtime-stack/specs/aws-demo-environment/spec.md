## ADDED Requirements

### Requirement: `envs/demo/` composes the six ephemeral modules

`infra/terraform/envs/demo/main.tf` SHALL declare exactly six
`module` blocks instantiating, in order, `network`, `data`, `auth`,
`secrets`, `compute`, `observability` from `infra/terraform/modules/`.
Inter-module wiring SHALL pass: VPC ID + private subnets + security
group IDs from `network` → `data` and `compute`; RDS endpoint +
credentials from `data` → `secrets`; user pool / client IDs from
`auth` → `secrets`; SSM parameter ARNs from `secrets` → `compute`;
ALB ARN and RDS endpoint from `compute` and `data` →
`observability`.

#### Scenario: `terraform apply` brings up every module

- **WHEN** `terraform -chdir=infra/terraform/envs/demo apply -auto-approve`
  is invoked against a clean AWS account with the bootstrap state
  backend already provisioned and a published image in ECR
- **THEN** the apply SHALL succeed within 25 minutes and SHALL
  create the resources declared by all six modules

### Requirement: S3 remote backend keyed at `envs/demo/terraform.tfstate`

`infra/terraform/envs/demo/backend.tf` SHALL declare:

```hcl
terraform {
  backend "s3" {
    bucket         = "nica-erp-tf-state"
    key            = "envs/demo/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "nica-erp-tf-lock"
    encrypt        = true
  }
}
```

#### Scenario: Concurrent apply attempts lock each other out

- **WHEN** two operators run `terraform apply` against
  `envs/demo/` simultaneously
- **THEN** the second invocation SHALL block on the DynamoDB
  `nica-erp-tf-lock` lock and SHALL NOT proceed until the first
  finishes

### Requirement: CloudFront `/api/*` origin is updated to the ALB DNS name

`envs/demo/main.tf` SHALL declare a resource that updates the
existing bootstrap-owned CloudFront distribution's `api-placeholder`
origin so that its `DomainName` equals the ALB DNS name produced by
the compute module. The resource SHALL include
`lifecycle { ignore_changes = [default_cache_behavior, custom_error_response, origin[?id == "web-s3"]] }`
(or an equivalent set of `ignore_changes` expressions) so that no
attribute owned by the bootstrap root is mutated. The behavior's
path pattern (`/api/*`), cache policy, origin-request policy, and
allowed methods SHALL remain unchanged from
`add-terraform-state-backend`.

#### Scenario: `/api/healthz` reaches the ALB after apply

- **WHEN** `terraform apply` finishes and at least 5 minutes have
  passed for CloudFront propagation
- **THEN** `curl https://<dist-id>.cloudfront.net/api/healthz`
  SHALL return HTTP 200 and a JSON body containing
  `"db":"ok"` and a non-null `alembic_revision`

#### Scenario: Default `/` behavior still serves the SPA bucket

- **WHEN** the same `curl` is repeated against `https://<dist-id>.cloudfront.net/`
- **THEN** the response SHALL still serve the `index.html` previously
  uploaded by `add-terraform-state-backend`-era verification,
  unaffected by the `/api/*` origin update

### Requirement: `terraform destroy` removes every demo-env resource

`terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`
SHALL delete every resource declared by the six modules and SHALL
revert the CloudFront `/api/*` origin to the
`placeholder.invalid` value declared by
`add-terraform-state-backend`. After completion, the Resource
Groups Tagging API filtered by `Project=nica-erp` SHALL return
only the bootstrap resources.

#### Scenario: Destroy returns the account to a bootstrap-only state

- **WHEN** `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`
  finishes
- **AND** `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`
  is called
- **THEN** the response SHALL contain exactly the bootstrap
  resources (`nica-erp-tf-state`, `nica-erp-tf-lock`, `nica-erp`
  ECR, `nica-erp-web`, the bootstrap CloudFront distribution)
  and no others
