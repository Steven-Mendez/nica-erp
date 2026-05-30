## ADDED Requirements

### Requirement: `update_active_tenant` calls `AdminUpdateUserAttributes` exactly once

`IdentityProviderCognito.update_active_tenant(*, external_sub,
tenant_id)` SHALL invoke the underlying boto3 client's
`admin_update_user_attributes(...)` method exactly once with:

- `UserPoolId=<the configured user pool id>`
- `Username=<external_sub>` (Cognito accepts the `sub` here for
  pool-with-username-aliases configurations; sprint 02 already
  validates this against the live pool)
- `UserAttributes=[{"Name": "custom:active_tenant", "Value":
  str(tenant_id)}]`

No other Cognito calls SHALL be made in the method body.

#### Scenario: Mocked client records one call with the right shape

- **GIVEN** an `IdentityProviderCognito` constructed with a mocked
  `cognito-idp` client
- **WHEN** `await idp.update_active_tenant(external_sub="abc",
  tenant_id="<T>")` is awaited
- **THEN** the mock SHALL have been called exactly once, the
  `Username` argument SHALL equal `"abc"`, and the
  `UserAttributes` argument SHALL include exactly the pair
  `("custom:active_tenant", "<T>")`

### Requirement: Cognito non-existent user is surfaced, not swallowed

If `AdminUpdateUserAttributes` raises `UserNotFoundException`,
`update_active_tenant` SHALL re-raise as
`IdentityProviderError` (or the canonical adapter-error type used
by sprint 02 for unexpected Cognito failures). The use case
`SwitchActiveTenant` catches no such exception and surfaces it as
500 — the situation indicates a desync between `tenant_members`
and the Cognito user pool that requires operator intervention.

#### Scenario: `UserNotFoundException` propagates

- **WHEN** the mocked client raises `UserNotFoundException`
- **THEN** `update_active_tenant` SHALL propagate the exception
  (wrapped or raw, per sprint 02's adapter-error convention)
