## ADDED Requirements

### Requirement: Bootstrap declares one GitHub OIDC provider

The bootstrap Terraform root SHALL declare exactly one
`aws_iam_openid_connect_provider` resource with
`url = "https://token.actions.githubusercontent.com"` and
`client_id_list = ["sts.amazonaws.com"]`. The provider SHALL carry
`tags = { Project = "nica-erp" }`. Its ARN SHALL be exposed as the
Terraform output `github_oidc_provider_arn`.

#### Scenario: OIDC provider exists after bootstrap

- **WHEN** `terraform -chdir=infra/terraform/bootstrap output -raw github_oidc_provider_arn`
  is executed after `make bootstrap`
- **THEN** the command SHALL print an ARN of the form
  `arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com`

### Requirement: Bootstrap declares the deploy and destroy IAM roles

The bootstrap Terraform root SHALL declare exactly two
`aws_iam_role` resources, `nica-erp-ci-deploy` and
`nica-erp-ci-destroy`. Each role's trust policy SHALL bind the
federated principal
`aws_iam_openid_connect_provider.github.arn` to subjects matching
`repo:Steven-Mendez/nica-erp:ref:refs/heads/main` only. Each role's
ARN SHALL be exposed as a Terraform output named
`ci_deploy_role_arn` and `ci_destroy_role_arn` respectively.

#### Scenario: Main-branch workflow can assume either role

- **WHEN** a workflow on `refs/heads/main` of
  `Steven-Mendez/nica-erp` requests
  `sts:AssumeRoleWithWebIdentity` against either role
- **THEN** AWS SHALL return temporary credentials whose policy is
  the role's inline policy

#### Scenario: Feature-branch workflow is rejected

- **WHEN** a workflow on `refs/heads/feature/foo` requests
  `AssumeRoleWithWebIdentity` against either role
- **THEN** AWS SHALL deny the request because the `sub` claim does
  not match the trust policy

### Requirement: Deploy role's inline policy covers the full deploy surface

`nica-erp-ci-deploy`'s inline policy SHALL grant:

- `ecr:GetAuthorizationToken` on `Resource: "*"` plus the ECR push
  actions (`ecr:BatchCheckLayerAvailability`, `ecr:BatchGetImage`,
  `ecr:CompleteLayerUpload`, `ecr:DescribeRepositories`,
  `ecr:InitiateLayerUpload`, `ecr:PutImage`, `ecr:UploadLayerPart`)
  scoped to `aws_ecr_repository.api.arn`.
- The Terraform-state actions on the state bucket
  (`s3:GetObject`, `s3:PutObject`, `s3:ListBucket`) and the lock
  table (`dynamodb:GetItem`, `dynamodb:PutItem`,
  `dynamodb:DeleteItem`).
- The apply-side AWS actions for the ephemeral resource set
  (VPC, RDS, ECS, ALB, Cognito, SSM, observability) as required
  by the ephemeral Terraform root in
  `add-aws-runtime-stack`.
- `s3:PutObject` + `s3:DeleteObject` on the SPA bucket
  (`nica-erp-web-*`) and `cloudfront:CreateInvalidation` on the
  bootstrap CloudFront distribution ARN.

The role SHALL NOT grant `s3:DeleteBucket`,
`ecr:DeleteRepository`, `cloudfront:DeleteDistribution`,
`iam:DeleteOpenIDConnectProvider`, or any other bootstrap-surface
mutation.

#### Scenario: Deploy role cannot delete the state bucket

- **WHEN** a workflow assumes `nica-erp-ci-deploy` and calls
  `aws s3api delete-bucket --bucket nica-erp-tf-state-<account-id>`
- **THEN** AWS SHALL deny the request with `AccessDenied`

### Requirement: Destroy role's inline policy covers only the ephemeral surface

`nica-erp-ci-destroy`'s inline policy SHALL grant the destroy-side
AWS actions on the ephemeral resource set (the same surface as
`ci-deploy` but with the destroy verbs) plus Terraform-state
read/write. The grant SHALL include `iam:DeleteRole` and
`iam:DeleteRolePolicy` at `Resource: "*"` because the ephemeral
stack creates IAM roles (the ECS task execution role and task
role) that `terraform destroy` must remove. The role SHALL carry
two explicit `Deny` statements that fence in those broad grants:

1. A `DenyBootstrapDestructive` statement that denies, at
   `Resource: "*"`, the bootstrap-surface mutations
   `s3:DeleteBucket`, `s3:DeleteBucketPolicy`,
   `ecr:DeleteRepository`, `cloudfront:DeleteDistribution`,
   `cloudfront:DeleteOriginAccessControl`,
   `iam:DeleteOpenIDConnectProvider`, and
   `iam:UpdateOpenIDConnectProviderThumbprint`.
2. A `DenyCiRoleMutation` statement that denies `iam:DeleteRole`,
   `iam:DeleteRolePolicy`, `iam:UpdateAssumeRolePolicy`,
   `iam:PutRolePolicy`, `iam:AttachRolePolicy`, and
   `iam:DetachRolePolicy` scoped to exactly the two role ARNs
   `arn:aws:iam::<account-id>:role/nica-erp-ci-deploy` and
   `arn:aws:iam::<account-id>:role/nica-erp-ci-destroy`.

The first Deny keeps the bootstrap-surface assets safe; the second
prevents `ci-destroy` from rewriting its own policy or tampering
with `ci-deploy`. Together they leave the ephemeral-stack IAM
roles deletable (required for `terraform destroy`) without
exposing the CI roles themselves to mutation.

#### Scenario: Destroy role cannot delete the OIDC provider

- **WHEN** a workflow assumes `nica-erp-ci-destroy` and calls
  `aws iam delete-open-id-connect-provider`
- **THEN** AWS SHALL deny the request with `AccessDenied`

#### Scenario: Destroy role cannot delete itself or the deploy role

- **WHEN** a workflow assumes `nica-erp-ci-destroy` and calls
  `aws iam delete-role --role-name nica-erp-ci-deploy` or
  `aws iam delete-role --role-name nica-erp-ci-destroy`
- **THEN** AWS SHALL deny the request with `AccessDenied`

#### Scenario: Destroy role can delete ephemeral-stack IAM roles

- **WHEN** `terraform destroy` running under `nica-erp-ci-destroy`
  removes the ECS task execution role created by the ephemeral
  stack
- **THEN** the `iam:DeleteRole` call SHALL succeed because the
  `DenyCiRoleMutation` Deny is scoped to the two CI role ARNs
  only

#### Scenario: Destroy role can destroy the ephemeral stack

- **WHEN** a workflow assumes `nica-erp-ci-destroy` and runs
  `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`
- **THEN** the operation SHALL succeed and the ephemeral resource
  set (VPC, RDS, ECS, ALB, Cognito, SSM, observability) SHALL be
  removed from the account

### Requirement: Bootstrap script prints role ARNs and the gh-variable commands

After `terraform apply` succeeds, `scripts/bootstrap.sh` SHALL
print the value of `github_oidc_provider_arn`, `ci_deploy_role_arn`,
and `ci_destroy_role_arn` alongside the existing bootstrap outputs.
It SHALL then print two literal commands:
`gh variable set AWS_DEPLOY_ROLE_ARN --body "<deploy-arn>"` and
`gh variable set AWS_DESTROY_ROLE_ARN --body "<destroy-arn>"`,
ready for the administrator to copy-paste.

#### Scenario: Operator sees a paste-ready checklist after bootstrap

- **WHEN** `make bootstrap` succeeds against an account with no
  prior bootstrap
- **THEN** stdout SHALL contain two lines beginning with
  `gh variable set AWS_DEPLOY_ROLE_ARN` and
  `gh variable set AWS_DESTROY_ROLE_ARN`, each ending with the
  matching ARN reported by `terraform output`

### Requirement: OIDC provider and roles tear down with the bootstrap

The OIDC provider and the two IAM roles SHALL be destroyed by the
same `terraform destroy` that `scripts/destroy-bootstrap.sh`
invokes. No role or provider SHALL outlive a successful
destroy-bootstrap run.

#### Scenario: destroy-bootstrap removes the OIDC provider and roles

- **WHEN** `make destroy-bootstrap` finishes successfully
- **THEN** `aws iam list-open-id-connect-providers` SHALL NOT
  include the `token.actions.githubusercontent.com` provider in
  the account
- **AND** `aws iam get-role --role-name nica-erp-ci-deploy` SHALL
  fail with `NoSuchEntity`
- **AND** `aws iam get-role --role-name nica-erp-ci-destroy` SHALL
  fail with `NoSuchEntity`
