## ADDED Requirements

### Requirement: `update_active_tenant` is reflected by the next minted JWT

`IdentityProviderLocal.update_active_tenant(*, external_sub,
tenant_id)` SHALL mutate the `auth_local_users.attributes` JSONB
column for `external_sub`, setting
`attributes['custom:active_tenant']` to `str(tenant_id)`. Every
subsequent JWT minted via `authenticate(...)`, `refresh(...)`, or
internal-mint paths SHALL carry the new value in the
`custom:active_tenant` claim.

#### Scenario: Refresh-after-update mints the new claim

- **GIVEN** a local user authenticated with `custom:active_tenant=""`
- **WHEN** `update_active_tenant(external_sub=<sub>,
  tenant_id=<T>)` is awaited and then `refresh(refresh_token=...)`
  is awaited
- **THEN** the new `Identity.claims["custom:active_tenant"]` SHALL
  equal `str(<T>)`

### Requirement: `forge_jwt` testing helper is available next to the adapter

`contexts.identity.testing.forge_jwt(*, user_id, email,
active_tenant, secret, aud="nica-erp-local", iss="nica-erp-local-idp",
ttl_seconds=3600, **extra_claims) -> str` SHALL produce an HS256
JWT whose claim shape exactly matches what
`IdentityProviderLocal.authenticate()` emits: `sub`, `email`,
`email_verified=True`, `custom:active_tenant`, `aud`, `iss`, `exp`,
`iat`. The helper SHALL be importable from any module under
`apps/api/tests/`. It SHALL NOT be importable from
`contexts/*/adapters/`, `contexts/*/application/`, or `bootstrap/`
— enforced by import-linter.

#### Scenario: Helper produces a middleware-acceptable token

- **WHEN** a test calls `forge_jwt(user_id=u, email="x@y.io",
  active_tenant=<T>, secret=LOCAL_JWT_SECRET)` and passes the
  result through `IdentityProviderLocal.verify_token(token=...)`
- **THEN** the decode SHALL succeed and the returned claims SHALL
  carry `sub=str(u)`, `email="x@y.io"`, and
  `custom:active_tenant=str(<T>)`

### Requirement: Helper supports the isolation gate test "forged tenant" case

`forge_jwt` SHALL accept an `active_tenant` UUID that has no
matching membership for `user_id`; the helper itself SHALL NOT
validate against `tenant_members`. Membership validation is the
job of `TenantMiddleware`, which the gate test exercises by
issuing a forged token and asserting 403.

#### Scenario: Forged-tenant token is syntactically valid

- **WHEN** `forge_jwt(user_id=<B>, active_tenant=<A>, ...)` is
  produced where B is not a member of A
- **THEN** the token SHALL decode successfully and only fail at
  the middleware membership check
