## MODIFIED Requirements

### Requirement: Invitation acceptance SHALL receive the token in the request body

The endpoint `POST /v1/invitations/accept` SHALL accept a JSON request body of shape `{ "token": "<token>" }`. It SHALL be allow-listed by the no-tenant middleware (an authenticated user without an active tenant can still call it; an unauthenticated request is rejected with `401`). On success it SHALL reuse the `AcceptInvitation` use case and return `200 OK` with the joined membership.

The legacy endpoint `POST /v1/invitations/{token}/accept` SHALL respond `410 Gone` with a problem body of shape `{ "type": "invitation-endpoint-moved", "title": "Invitation endpoint moved", "location": "/v1/invitations/accept" }` and SHALL NOT execute the `AcceptInvitation` use case.

#### Scenario: New body endpoint accepts a valid token

- **GIVEN** an authenticated user with a pending, unexpired invitation for their email
- **WHEN** they call `POST /v1/invitations/accept` with body `{"token": "<valid token>"}`
- **THEN** the response status SHALL be `200` and the response body SHALL describe the new membership

#### Scenario: Legacy path returns 410 Gone

- **GIVEN** any caller (authenticated or not)
- **WHEN** they call `POST /v1/invitations/<token>/accept` with any body
- **THEN** the response status SHALL be `410` and the body's `type` SHALL be `invitation-endpoint-moved`

### Requirement: Invitation preview endpoint SHALL expose limited metadata under rate limit

The endpoint `GET /v1/invitations/{token}/preview` SHALL be public (no authentication required), SHALL return `{ "email": "<string>", "organization_name": "<string>", "role": "<string>" }` for a valid, unexpired token, and SHALL be rate-limited to at most one request per second per token (in-memory token bucket is acceptable for MVP). The endpoint MUST NOT return any field that is not already present in the original invitation email body.

#### Scenario: Valid token returns the three preview fields

- **GIVEN** a pending invitation for `b@test.dev` to organization "Empresa A" with role `accountant`
- **WHEN** an unauthenticated caller invokes `GET /v1/invitations/<token>/preview`
- **THEN** the response status SHALL be `200` and the body SHALL equal `{"email": "b@test.dev", "organization_name": "Empresa A", "role": "accountant"}`

#### Scenario: Rate-limit returns 429 on burst

- **GIVEN** ten concurrent calls to `GET /v1/invitations/<token>/preview` for the same token
- **WHEN** the calls land within one second
- **THEN** at least one call SHALL receive `429 Too Many Requests` with a `Retry-After` header

#### Scenario: Expired token returns 404

- **GIVEN** an invitation whose `expires_at` is in the past
- **WHEN** `GET /v1/invitations/<token>/preview` is called
- **THEN** the response status SHALL be `404`

### Requirement: Invitation email URL SHALL place the token in a URL fragment

The `_DEFAULT_INVITE_URL_TEMPLATE` constant in `apps/api/src/contexts/tenants/adapters/inbound/http/router.py` SHALL be `https://<host>/invitations/accept#t={token}` (with `<host>` resolved by the configured frontend base URL). The email template SHALL render the URL exactly with this shape; in particular the `#` SHALL precede `t=` and the token SHALL be the last component of the URL.

#### Scenario: Rendered invitation email contains the fragment

- **GIVEN** the email sender is invoked with `token = "abc.def.ghi"` and frontend base URL `https://erp.example.com`
- **WHEN** the rendered email body is inspected
- **THEN** it SHALL contain the substring `https://erp.example.com/invitations/accept#t=abc.def.ghi`
- **AND** it SHALL NOT contain the substring `https://erp.example.com/invitations/abc.def.ghi/accept`
