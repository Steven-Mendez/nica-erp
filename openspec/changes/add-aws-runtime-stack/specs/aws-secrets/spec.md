## ADDED Requirements

### Requirement: SSM parameters carry runtime configuration

The `infra/terraform/modules/secrets/` module SHALL declare the
following SSM parameters, all with KMS key alias `alias/aws/ssm`
and tag `Project=nica-erp`:

- `/nica-erp/demo/rds/url` — type `SecureString`, value sourced from
  the data module.
- `/nica-erp/demo/rds/username` — type `SecureString`.
- `/nica-erp/demo/rds/password` — type `SecureString`.
- `/nica-erp/demo/cognito/user-pool-id` — type `String`, value
  sourced from the auth module.
- `/nica-erp/demo/cognito/client-id` — type `String`.

#### Scenario: All five parameters exist

- **WHEN** `aws ssm describe-parameters --filters Key=Name,Values=/nica-erp/demo/`
  is called after apply
- **THEN** the response SHALL list at least the five parameters
  above, with `Type` matching the spec

### Requirement: `LOCAL_JWT_SECRET` placeholder is empty in AWS

The module SHALL declare a single SSM SecureString parameter
`/nica-erp/demo/jwt/secret` with `value=""`. The Terraform resource
SHALL set `lifecycle { ignore_changes = [value] }` so an operator
can later overwrite the value via `aws ssm put-parameter` without
Terraform reverting it.

#### Scenario: Empty placeholder exists

- **WHEN** `aws ssm get-parameter --name /nica-erp/demo/jwt/secret --with-decryption`
  is called immediately after apply
- **THEN** the response SHALL include `Value=""`

#### Scenario: Operator override survives `terraform apply`

- **WHEN** an operator overwrites the parameter via
  `aws ssm put-parameter --name /nica-erp/demo/jwt/secret --value "live-secret" --type SecureString --overwrite`
  and then runs `terraform apply` against the demo env
- **THEN** the apply SHALL report no changes for the parameter and
  the value SHALL remain `"live-secret"`
