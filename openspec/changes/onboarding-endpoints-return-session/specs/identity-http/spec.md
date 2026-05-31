## MODIFIED Requirements

### Requirement: `POST /v1/auth/confirm-signup` SHALL accept an optional `password` and return a session bundle when present

The endpoint `POST /v1/auth/confirm-signup` SHALL accept a JSON request body of shape
`{ "email": "<string>", "code": "<string>", "password": "<string>" | null }`,
where `password` is optional. The endpoint SHALL stay on the no-auth allow-list of
the request middleware (an unauthenticated caller can invoke it).

When `password` is **absent** or `null`, the endpoint SHALL preserve its current
`204 No Content` shape: it SHALL confirm the email code via the
`IdentityProvider`, create the `User` aggregate, write the
`identity.UserRegistered v1` event to the outbox in the same transaction, and
respond `204` with an empty body.

When `password` is **present**, the endpoint SHALL additionally invoke
`IdentityProvider.authenticate(email, password)` in the same transaction and
respond `200 OK` with a JSON body of the same shape used by
`POST /v1/auth/login`:
`{ "access_token": "<jwt>", "refresh_token": "<jwt>", "id_token": "<jwt>", "expires_in": <int>, "token_type": "Bearer" }`.
The endpoint MUST NOT log the `password` field or echo it in any error response,
matching the redaction policy already enforced for `POST /v1/auth/login`.

If the code is invalid, the endpoint SHALL respond `400` (current behaviour)
**regardless** of whether `password` is supplied. If the code is valid but the
subsequent `authenticate` call rejects the password, the email confirmation and
the user aggregate creation SHALL remain committed (because the email code has
already been consumed at the `IdentityProvider` and is no longer replayable),
and the endpoint SHALL respond `401` with `application/problem+json` per
[ADR-0015](../../../../../docs/adr/0015-rfc7807-errors.md). The caller MAY
recover by calling `POST /v1/auth/login` with the corrected password; no second
email code is required.

#### Scenario: Bare confirm without password returns 204

- **GIVEN** an account that was registered via `POST /v1/auth/register` and a fresh email code
- **WHEN** the SPA calls `POST /v1/auth/confirm-signup` with body `{"email": "yo@test.dev", "code": "123456"}`
- **THEN** the response status SHALL be `204` and the response body SHALL be empty
- **AND** a follow-up `POST /v1/auth/login` with the registered password SHALL succeed and return tokens

#### Scenario: Confirm with password returns a token bundle

- **GIVEN** an account that was registered via `POST /v1/auth/register` and a fresh email code
- **WHEN** the SPA calls `POST /v1/auth/confirm-signup` with body `{"email": "yo@test.dev", "code": "123456", "password": "Demo1234!@"}`
- **THEN** the response status SHALL be `200`
- **AND** the response body SHALL include `access_token`, `refresh_token`, and `id_token` as non-empty strings
- **AND** a follow-up `GET /v1/me` with the returned `access_token` SHALL return `200` with the freshly-created user

#### Scenario: Confirm with wrong password keeps the confirmation and returns 401

- **GIVEN** an account that was registered via `POST /v1/auth/register` and a fresh email code
- **WHEN** the SPA calls `POST /v1/auth/confirm-signup` with body `{"email": "yo@test.dev", "code": "123456", "password": "Wrong1234!"}`
- **THEN** the response status SHALL be `401` with content-type `application/problem+json`
- **AND** the user aggregate SHALL be persisted (the email code was consumed by the IdP and is no longer replayable)
- **AND** a follow-up `POST /v1/auth/login` with the correct password SHALL succeed without requiring a new email code

#### Scenario: Confirm request body redacts password in logs

- **GIVEN** any call to `POST /v1/auth/confirm-signup` with a `password` field
- **WHEN** the request is logged to CloudWatch / stdout
- **THEN** the log entry SHALL NOT include the value of the `password` field
- **AND** the redaction SHALL be the same mechanism used for `POST /v1/auth/login` request bodies
