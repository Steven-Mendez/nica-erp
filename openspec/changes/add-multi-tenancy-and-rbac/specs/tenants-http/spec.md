## ADDED Requirements

### Requirement: `/v1/tenants` router exposes the canonical tenant lifecycle

A FastAPI router mounted at `/v1/tenants` SHALL declare:

| Method | Path | Permission | Tenant required |
|---|---|---|---|
| `POST` | `/v1/tenants` | — (allowlisted) | No |
| `GET` | `/v1/tenants/me` | — | No |
| `GET` | `/v1/tenants/{id}` | `tenant:read` | Yes |
| `PATCH` | `/v1/tenants/{id}` | `tenant:write` | Yes |
| `POST` | `/v1/tenants/{id}/switch` | — | No (allowlisted; membership check inline) |
| `GET` | `/v1/tenants/{id}/members` | `members:read` | Yes |
| `PATCH` | `/v1/tenants/{id}/members/{user_id}` | `members:update-role` | Yes |
| `DELETE` | `/v1/tenants/{id}/members/{user_id}` | `members:remove` | Yes |
| `GET` | `/v1/tenants/{id}/invitations` | `members:read` | Yes |
| `POST` | `/v1/tenants/{id}/invitations` | `members:invite` | Yes |
| `DELETE` | `/v1/tenants/{id}/invitations/{invitation_id}` | `members:invite` | Yes |

Permission-bearing routes SHALL declare `Depends(require("<code>"))`
in the route signature so OpenAPI documents the requirement.

#### Scenario: Permission gate is declared on every protected route

- **WHEN** the FastAPI router is inspected for routes outside the
  no-tenant-required allowlist
- **THEN** each route SHALL have at least one
  `Depends(require(...))` in its dependency list

### Requirement: `POST /v1/tenants` creates a tenant and the owner membership

The endpoint accepts `{name: str, ruc: str, regime: "general"|"simplified",
municipality: str, authorization_dgi: {number: str, valid_from:
date, valid_to: date} | null, fiscal_address: str, is_withholder:
bool}`. On success it SHALL return HTTP 201 with body
`{id: UUID, name, ruc, regime, municipality, authorization_dgi,
fiscal_address, is_withholder, status: "active", created_at,
updated_at}`. Conflict on `ruc` SHALL surface as HTTP 409 with
`code="tenants.ruc_taken"`.

#### Scenario: Duplicate RUC returns 409

- **WHEN** two `POST /v1/tenants` requests share the same `ruc`
- **THEN** the second SHALL return 409 with
  `{"code": "tenants.ruc_taken"}`

### Requirement: `POST /v1/tenants/{id}/switch` returns a fresh `Identity`

The endpoint accepts `{refresh_token: string}` in the body. On
success it SHALL return HTTP 200 with body
`{access_token, refresh_token, id_token, token_type: "Bearer",
expires_in: int}`. The new tokens' `custom:active_tenant` claim
SHALL equal the path `{id}`. Membership absence SHALL surface as
HTTP 403 with `code="tenant.not_member"`.

#### Scenario: Non-member receives 403

- **WHEN** an authenticated user calls `POST /v1/tenants/{foreign_id}/switch`
- **THEN** the response SHALL be 403 with
  `{"code": "tenant.not_member"}` and NO tokens SHALL be issued

### Requirement: Member-management endpoints respect role hierarchy

`PATCH /v1/tenants/{id}/members/{user_id}` accepts `{role: "admin" |
"accountant" | "salesperson" | "viewer"}` and SHALL:

- reject `role="owner"` with HTTP 422 (request validation; owner is
  not in the role enum surfaced by the endpoint).
- reject demoting the current owner with HTTP 409
  `code="tenants.cannot_demote_owner"`.

`DELETE /v1/tenants/{id}/members/{user_id}` SHALL reject removing
the current owner with HTTP 409 `code="tenants.cannot_remove_owner"`.

#### Scenario: Demoting the owner is rejected

- **WHEN** an admin calls `PATCH /v1/tenants/{id}/members/{owner_user_id}`
  with `{role: "admin"}`
- **THEN** the response SHALL be 409 with
  `{"code": "tenants.cannot_demote_owner"}`

### Requirement: `POST /v1/tenants/{id}/invitations` mints a token and sends email

The endpoint accepts `{email: str, proposed_role: "admin" |
"accountant" | "salesperson" | "viewer"}`. It SHALL return HTTP 201
with `{id, email, proposed_role, status: "pending", expires_at}`.
The plaintext token SHALL NOT appear in the response (it is mailed
to the invitee). The response SHALL include the same
`Idempotency-Key` semantics as other state-changing POSTs (key
optional per [`docs/08-api-conventions.md`](../../../../docs/08-api-conventions.md)
§Idempotency).

#### Scenario: Plaintext token is not in the response

- **WHEN** `POST /v1/tenants/{id}/invitations` succeeds
- **THEN** the response body SHALL NOT contain a key whose value is
  the plaintext invitation token

### Requirement: `POST /v1/invitations/{token}/accept` is public

The route is in the unauthenticated allowlist (already from sprint
02). It accepts no body and SHALL return HTTP 200 with body
`{tenant_id: UUID, role: str}`. Acceptance preconditions
(invitation expired, already accepted, cancelled, invalid
signature) SHALL surface as HTTP 410 Gone with codes
`invitation.expired`, `invitation.already_accepted`,
`invitation.cancelled`, `invitation.invalid` respectively.

#### Scenario: Expired invitation returns 410

- **WHEN** a user calls `POST /v1/invitations/{expired_token}/accept`
- **THEN** the response SHALL be 410 with
  `{"code": "invitation.expired"}`

### Requirement: RFC-7807 error mapping is stable

The router SHALL surface domain errors via
`application/problem+json` with stable codes:

| Exception | HTTP | code |
|---|---|---|
| `TenantNotFoundError` | 404 | `tenants.not_found` |
| `NotAMemberError` | 403 | `tenant.not_member` |
| `OwnerAlreadyExistsError` | 409 | `tenants.owner_already_exists` |
| `CannotRemoveOwnerError` | 409 | `tenants.cannot_remove_owner` |
| `CannotDemoteOwnerError` | 409 | `tenants.cannot_demote_owner` |
| `InvitationExpiredError` | 410 | `invitation.expired` |
| `InvitationAlreadyAcceptedError` | 410 | `invitation.already_accepted` |
| `InvitationCancelledError` | 410 | `invitation.cancelled` |
| `InvitationInvalidError` | 410 | `invitation.invalid` |
| `ForbiddenError` (from `require(...)`) | 403 | `missing-permission` |

#### Scenario: Forbidden error includes the missing codes

- **WHEN** a `viewer` calls `PATCH /v1/tenants/{id}` and the
  `require("tenant:write")` dependency raises
- **THEN** the 403 problem body SHALL include the extension
  `"missing": ["tenant:write"]`
