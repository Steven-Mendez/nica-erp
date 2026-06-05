# aws-auth Specification

## Purpose
TBD - created by archiving change add-aws-runtime-stack. Update Purpose after archive.
## Requirements
### Requirement: Cognito User Pool with `custom:active_tenant` from day one

The `infra/terraform/modules/auth/` module SHALL create one
`aws_cognito_user_pool` named `nica-erp-demo` with the schema
attribute `custom:active_tenant` declared as `String`, `Mutable=true`,
no minimum length, no maximum length; default value MUST be empty
(unset). The pool SHALL allow self-service sign-up disabled by
default, require email as username
(`username_attributes=["email"]`), and carry the tag
`Project=nica-erp`.

#### Scenario: Custom attribute is declared

- **WHEN** `aws cognito-idp describe-user-pool --user-pool-id <pool>`
  is called after apply
- **THEN** the response's `Schema` array SHALL include an entry with
  `Name="custom:active_tenant"`, `AttributeDataType="String"`,
  `Mutable=true`

#### Scenario: Empty default lets new users sign in without a tenant

- **WHEN** a new user is created via `aws cognito-idp admin-create-user`
  without specifying `custom:active_tenant`
- **THEN** the user SHALL be created successfully and the attribute
  SHALL be absent from the user's record

### Requirement: SPA app client without secret

The module SHALL create one `aws_cognito_user_pool_client` named
`nica-erp-spa` with `generate_secret=false`,
`allowed_oauth_flows=["code"]`,
`allowed_oauth_scopes=["openid","email","profile"]`,
`allowed_oauth_flows_user_pool_client=true`,
`supported_identity_providers=["COGNITO"]`. The client SHALL declare
`callback_urls = ["https://${aws_cloudfront_distribution.main.domain_name}/auth/callback"]`
and `logout_urls =
["https://${aws_cloudfront_distribution.main.domain_name}/auth/callback"]`,
sourcing the CloudFront distribution attribute directly so no prior
`terraform apply` is required for the value to resolve. MVP does not
consume these callbacks (no Hosted UI); they are pre-wired so a later
sprint can opt into OAuth flows without an app client mutation.

#### Scenario: Public client cannot issue secret-based requests

- **WHEN** `aws cognito-idp describe-user-pool-client --user-pool-id <pool> --client-id <client>`
  is called
- **THEN** the response SHALL NOT include a `ClientSecret` field

#### Scenario: Callback URL is `/auth/callback`

- **WHEN** `aws cognito-idp describe-user-pool-client --user-pool-id <pool> --client-id <client>`
  is invoked after apply
- **THEN** the `CallbackURLs` array SHALL contain exactly one entry
  ending in `/auth/callback`

#### Scenario: Logout URL matches the callback URL

- **WHEN** the same describe call is inspected
- **THEN** the `LogoutURLs` array SHALL contain the same single
  CloudFront-domain entry ending in `/auth/callback`

### Requirement: Default-prefix user pool domain exposes JWKS

The module SHALL create one `aws_cognito_user_pool_domain` whose
`domain` is the variable `cognito_domain_prefix` (default
`nica-erp`) and `user_pool_id` references the pool above. The
module SHALL NOT attach a custom domain or ACM certificate.

#### Scenario: JWKS endpoint is reachable

- **WHEN** `curl https://nica-erp.auth.us-east-1.amazoncognito.com/.well-known/jwks.json`
  is invoked after apply
- **THEN** the response SHALL be HTTP 200 with a JSON body containing
  a `keys` array of length `>= 1`

