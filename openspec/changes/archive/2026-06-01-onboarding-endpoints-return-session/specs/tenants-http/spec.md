## MODIFIED Requirements

### Requirement: `POST /v1/invitations/accept` SHALL rotate session tokens for first-membership invitees

The endpoint `POST /v1/invitations/accept` SHALL accept a JSON request body of
shape `{ "token": "<string>", "refresh_token": "<string>" | null }`, where
`refresh_token` is optional. The endpoint SHALL remain on the no-active-tenant
allow-list of the request middleware: an authenticated caller whose JWT lacks
`custom:active_tenant` can still invoke it; an unauthenticated request SHALL
be rejected with `401`.

The response SHALL be a JSON body of shape
`{ "tenant_id": "<uuid>", "role": "<role>", "tokens": <bundle> | null }` where
`tokens`, when non-null, SHALL be a `{ access_token, refresh_token, id_token,
expires_in, token_type }` object identical in shape to the response of
`POST /v1/auth/login`.

The decision to populate `tokens` SHALL be derived from the **validated**
`CurrentUserContext.active_tenant` of the bearer token, NOT from any value in the
request body. Concretely:

- When the caller's `CurrentUserContext.active_tenant` is **null** AND a
  non-empty `refresh_token` is present in the request body, the use case SHALL
  call `IdentityProvider.update_active_tenant(user_id, tenant_id)` followed by
  `IdentityProvider.refresh(refresh_token)` and return the resulting bundle in
  the `tokens` field of the response.
- When the caller's `CurrentUserContext.active_tenant` is **not null**, the use
  case SHALL NOT call `update_active_tenant` or `refresh`, the `tokens` field
  of the response SHALL be `null`, and the caller's session SHALL remain bound
  to the empresa it was already bound to.
- When the caller's `CurrentUserContext.active_tenant` is **null** but no
  `refresh_token` is supplied in the request body, the `tokens` field SHALL be
  `null` and the caller's JWT SHALL still lack `custom:active_tenant` after the
  call. The caller is expected to acquire a session-ready JWT through
  `POST /v1/tenants/{id}/switch` as before.

In every case the `Membership` SHALL be persisted in the same transaction as
before and the `tenants.MemberJoined v1` event SHALL be written to the outbox.

#### Scenario: First-membership invitee receives rotated tokens

- **GIVEN** an authenticated user `U` whose JWT has no `custom:active_tenant` claim, a pending invitation `I` for `U` to tenant `T`, and `U`'s current refresh token `R`
- **WHEN** the SPA calls `POST /v1/invitations/accept` with body `{"token": "<I.token>", "refresh_token": "<R>"}`
- **THEN** the response status SHALL be `200`
- **AND** the response body SHALL include `tenant_id == T`, `role == I.role`, and a non-null `tokens` object
- **AND** decoding `tokens.access_token` SHALL show `custom:active_tenant == T`
- **AND** a follow-up `GET /v1/me` with the new access token SHALL show `T` as the active empresa
- **AND** a follow-up `GET /v1/tenants/<T>/invitations` with the new access token SHALL return `200` (not `403`)

#### Scenario: Veteran caller accepting a second-empresa invitation preserves the active empresa

- **GIVEN** an authenticated user `U` whose JWT already has `custom:active_tenant == A`, a pending invitation `I` for `U` to a different tenant `B`, and `U`'s current refresh token `R`
- **WHEN** the SPA calls `POST /v1/invitations/accept` with body `{"token": "<I.token>", "refresh_token": "<R>"}`
- **THEN** the response status SHALL be `200`
- **AND** the response body SHALL include `tenant_id == B`, `role == I.role`, and `tokens == null`
- **AND** a follow-up `GET /v1/me` with the same (unrotated) access token SHALL still show `A` as the active empresa
- **AND** the `Membership` for `(U, B)` SHALL exist with status `joined`

#### Scenario: First-membership invitee without refresh token does not rotate

- **GIVEN** an authenticated user `U` whose JWT has no `custom:active_tenant` claim and a pending invitation `I` for `U` to tenant `T`
- **WHEN** the SPA calls `POST /v1/invitations/accept` with body `{"token": "<I.token>"}` (no `refresh_token`)
- **THEN** the response status SHALL be `200` and the response body SHALL include `tenant_id == T`, `role == I.role`, and `tokens == null`
- **AND** the `Membership` SHALL be persisted
- **AND** a follow-up `POST /v1/tenants/<T>/switch` SHALL succeed and mint tokens with `custom:active_tenant == T`

#### Scenario: Spoofed prior-tenant claim cannot suppress rotation

- **GIVEN** an authenticated user `U` whose validated bearer token has `custom:active_tenant == null` (no prior tenant), and a request body that somehow includes a fake `prior_active_tenant` field
- **WHEN** the SPA calls `POST /v1/invitations/accept` with the body containing the fake field
- **THEN** the use case SHALL ignore the request-body field and consult only the validated `CurrentUserContext.active_tenant`
- **AND** when a `refresh_token` is supplied, the response SHALL still rotate tokens with the invited empresa as the active tenant
