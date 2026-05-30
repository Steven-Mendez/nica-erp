## ADDED Requirements

### Requirement: `user-pool-domain` SSM parameter

The `secrets/` module SHALL declare an SSM parameter at path
`/nica-erp/demo/cognito/user-pool-domain` of type `String` (not
`SecureString` — the domain is public) with value sourced from
`module.auth.user_pool_domain`. The KMS key alias SHALL be
`alias/aws/ssm` and the tag set SHALL include `Project=nica-erp`.

#### Scenario: Parameter exists post-apply

- **WHEN** `aws ssm get-parameter --name
  /nica-erp/demo/cognito/user-pool-domain` is invoked after apply
- **THEN** the response SHALL include `Type: "String"` and a `Value`
  ending in `.amazoncognito.com`

### Requirement: `ses/from-address` SSM parameter

The `secrets/` module SHALL declare an SSM parameter at path
`/nica-erp/demo/ses/from-address` of type `String` with value sourced
from `var.from_address` (the operator address). Projection of this
parameter into the API container's env var is owned by the
`aws-compute` capability (the ECS task definition lives in the
compute module).

#### Scenario: Parameter exists post-apply

- **WHEN** `aws ssm get-parameter --name
  /nica-erp/demo/ses/from-address` is invoked after apply
- **THEN** the response SHALL include `Type: "String"` and a `Value`
  containing `@`
