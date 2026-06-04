# invitation-identity-binding Specification

## Purpose
TBD - created by archiving change bind-invitation-accept-to-invitee-identity. Update Purpose after archive.
## Requirements
### Requirement: Invitation acceptance is bound to the invitee's authenticated identity

The `POST /v1/invitations/accept` endpoint SHALL compare the
invitation JWT's `sub` claim (the invitee email at issue time) against
the authenticated user's email, case-insensitively, BEFORE writing any
membership row or consuming the token's jti. On mismatch, the endpoint
SHALL reject the request with `403 Forbidden` and code
`invitation.identity_mismatch`. The detail field SHALL NOT echo the
JWT sub back to the requester.

#### Scenario: A logged-in user rejects an invitation issued to someone else

- **GIVEN** an invitation JWT issued for `accountant@audit.test` to
  tenant T1 with role `accountant`
- **AND** an authenticated session for `owner2@audit.test`
- **WHEN** `POST /v1/invitations/accept` is called with the token and
  `Authorization: Bearer <owner2's access token>`
- **THEN** the API SHALL respond `403 invitation.identity_mismatch`
- **AND** `owner2@audit.test`'s membership list SHALL NOT include T1
- **AND** the invitation's status SHALL remain `pending` (the jti
  SHALL NOT be marked accepted)

#### Scenario: The intended invitee accepts and joins

- **GIVEN** the same invitation JWT for `accountant@audit.test`
- **AND** the user `accountant@audit.test` has signed up and is
  authenticated
- **WHEN** `POST /v1/invitations/accept` is called with the token and
  the accountant's access token
- **THEN** the API SHALL respond `200 OK`
- **AND** `/v1/tenants/me` for `accountant@audit.test` SHALL include
  T1 with role `accountant`

#### Scenario: Case-insensitivity in the identity check

- **GIVEN** an invitation JWT with `sub:"Invitee@AUDIT.test"`
- **AND** an authenticated session for `invitee@audit.test`
- **WHEN** `POST /v1/invitations/accept` is called
- **THEN** the API SHALL respond `200 OK` (the comparison is
  case-insensitive)

