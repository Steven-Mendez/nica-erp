## ADDED Requirements

### Requirement: Explicit auth flows enabled for the SPA app client

The `aws_cognito_user_pool_client.nica-erp-spa` resource SHALL set
`explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH",
"ALLOW_REFRESH_TOKEN_AUTH"]`. `ALLOW_USER_SRP_AUTH` and
`ALLOW_ADMIN_USER_PASSWORD_AUTH` SHALL NOT be enabled in MVP. The
SPA does **not** call `InitiateAuth` directly — the API forwards
credentials over HTTPS — but Cognito still requires the flow to be
listed on the client.

#### Scenario: USER_PASSWORD_AUTH is enabled

- **WHEN** `aws cognito-idp describe-user-pool-client --user-pool-id
  <pool> --client-id <client>` is invoked after apply
- **THEN** the response's `ExplicitAuthFlows` array SHALL include
  `"ALLOW_USER_PASSWORD_AUTH"` and `"ALLOW_REFRESH_TOKEN_AUTH"`

#### Scenario: SRP is not enabled

- **WHEN** the same describe call is inspected
- **THEN** the `ExplicitAuthFlows` array MUST NOT include
  `"ALLOW_USER_SRP_AUTH"`

### Requirement: API Fargate task role gets the cognito-idp action allow-list

A policy MUST be attached to the API's Fargate task role (either by
the `auth/` module or by a downstream IAM module that consumes its
outputs) permitting the following `cognito-idp` actions on the user
pool ARN:
`SignUp`, `ConfirmSignUp`, `ResendConfirmationCode`, `InitiateAuth`,
`GlobalSignOut`, `ForgotPassword`, `ConfirmForgotPassword`,
`ChangePassword`, `AdminUpdateUserAttributes`, `AdminGetUser`. The
policy MUST NOT include any destructive action (`AdminDeleteUser`,
`DeleteUserPool*`, `AdminSetUserPassword`).

#### Scenario: Allow-list matches the spec

- **WHEN** `aws iam get-role-policy --role-name nica-erp-api-task ...`
  is invoked after apply
- **THEN** the policy `Statement[*].Action` SHALL be exactly the ten
  actions listed above

#### Scenario: Destructive actions are not granted

- **WHEN** the same policy is inspected
- **THEN** the `Statement[*].Action` MUST NOT include
  `"cognito-idp:AdminDeleteUser"` or `"cognito-idp:DeleteUserPool"`
  or `"cognito-idp:AdminSetUserPassword"`

### Requirement: Token validities pinned to one hour for access and ID

The `aws_cognito_user_pool_client.nica-erp-spa` resource SHALL set
`access_token_validity = 60`, `id_token_validity = 60`,
`refresh_token_validity = 30`, and `token_validity_units = { access_token
= "minutes", id_token = "minutes", refresh_token = "days" }`. This
matches the canonical TTLs in
[`docs/06-security-model.md` §TTLs](../../../../docs/06-security-model.md#ttls)
and avoids Cognito's default values (which differ across regions).

#### Scenario: Token validities match the security model

- **WHEN** `aws cognito-idp describe-user-pool-client --user-pool-id
  <pool> --client-id <client>` is invoked after apply
- **THEN** the response SHALL show `AccessTokenValidity=60`,
  `IdTokenValidity=60`, `RefreshTokenValidity=30`, and
  `TokenValidityUnits` matching the spec

### Requirement: User pool domain output

The `auth/` module SHALL expose an output `user_pool_domain` whose
value is the fully-qualified default-prefix URL
`nica-erp.auth.us-east-1.amazoncognito.com` (no scheme prefix). The
`secrets/` module SHALL consume this output to populate the SSM
parameter `/nica-erp/demo/cognito/user-pool-domain`.

#### Scenario: Output equals the documented default prefix

- **WHEN** `terraform output -raw user_pool_domain` is invoked in the
  `envs/demo` root
- **THEN** the output SHALL equal
  `"nica-erp.auth.us-east-1.amazoncognito.com"`

