## ADDED Requirements

### Requirement: `GET /v1/me` returns the actor's role and permissions

`GET /v1/me` SHALL extend the sprint-02 response with two
additional fields:

- `role: string | null` — the actor's role in the currently active
  tenant. `null` when no tenant is active (i.e. the user just
  signed up and hasn't picked / created a tenant yet).
- `permissions: string[]` — the materialized permission codes for
  `(role, tenant_id)` resolved through the TTL cache. Empty array
  when no tenant is active.

The endpoint's request shape SHALL NOT change; the additions are
strictly additive and do not bump `/v1` to `/v2` per
[ADR-0027](../../../../docs/adr/0027-api-versioning.md).

#### Scenario: Authenticated user with no tenant active

- **GIVEN** a JWT for a freshly-confirmed user with empty
  `custom:active_tenant`
- **WHEN** the user calls `GET /v1/me`
- **THEN** the response SHALL include `"role": null` and
  `"permissions": []` alongside the sprint-02 profile fields

#### Scenario: Admin in an active tenant lists permissions

- **GIVEN** an admin in tenant `<T>`
- **WHEN** the user calls `GET /v1/me`
- **THEN** the response SHALL include `"role": "admin"` and
  `"permissions"` whose sorted contents EQUAL the sorted contents
  of `DEFAULT_ROLE_PERMISSIONS["admin"]` at the time of the
  request

### Requirement: The HTTP layer composes the actor onto the response

The `get_me` use case in `contexts.identity.application` SHALL
remain identity-only (it does not import `contexts.tenants` or
`shared_kernel.permissions`). The router SHALL compose the
`role` / `permissions` fields by resolving the request's
`current_actor` dependency and overlaying it onto the
`MeResponse` schema. This keeps the cross-context coupling at
the HTTP layer, not in the use case.

#### Scenario: Identity application has no permissions import

- **GIVEN** the identity application package
- **WHEN** static analysis searches for imports of
  `shared_kernel.permissions.*` or `contexts.tenants.*`
- **THEN** the search SHALL return no matches under
  `contexts/identity/application/`

### Requirement: OpenAPI schema reflects the additive change

After this change, `openapi.json` for `GET /v1/me` SHALL declare
`role: { type: string, nullable: true }` and `permissions: { type:
array, items: { type: string } }` as response fields. The
generated TypeScript client (`apps/web/src/api/schema.d.ts`)
SHALL pick up the additions on the next `pnpm gen:api` run.

#### Scenario: Schema includes new fields

- **WHEN** `curl /openapi.json | jq '.paths."/v1/me".get.responses."200".content."application/json".schema.properties'`
  is inspected
- **THEN** the object SHALL contain keys `role` and `permissions`
  with the declared types
