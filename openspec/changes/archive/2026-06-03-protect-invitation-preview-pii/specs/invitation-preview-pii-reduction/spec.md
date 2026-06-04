## ADDED Requirements

### Requirement: Public invitation preview does not disclose the invitee email

The `GET /v1/invitations/{token}/preview` endpoint SHALL return only
the empresa name and the proposed role in its response body. The
invitee email SHALL NOT appear in the response at any time, regardless
of whether the caller is anonymous or authenticated. The accept screen
SHALL collect the email from the user via a typed input and submit it
to the server for comparison against the JWT `sub`.

#### Scenario: Anonymous preview omits email

- **GIVEN** a valid invitation token for `accountant@audit.test`
- **WHEN** an anonymous caller issues
  `GET /v1/invitations/<token>/preview`
- **THEN** the response SHALL be 200 with body
  `{"organization_name":"Empresa Auditoría Alfa","role":"accountant"}`
- **AND** the response body SHALL NOT include any field whose value is
  `accountant@audit.test`

#### Scenario: Accept with mismatching confirmed_email is rejected

- **GIVEN** a valid invitation token issued for
  `accountant@audit.test`
- **AND** an authenticated session for `accountant@audit.test`
- **WHEN** the SPA calls `POST /v1/invitations/accept` with
  `{token, confirmed_email:"intruder@evil.test"}`
- **THEN** the API SHALL respond `403 invitation.identity_mismatch`

#### Scenario: Accept with matching confirmed_email succeeds

- **GIVEN** the same token and the authenticated invitee
- **WHEN** the SPA calls accept with
  `{token, confirmed_email:"accountant@audit.test"}`
- **THEN** the API SHALL respond `200 OK` and the membership SHALL be
  created
