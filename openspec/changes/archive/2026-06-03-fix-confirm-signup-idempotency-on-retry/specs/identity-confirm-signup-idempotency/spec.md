## ADDED Requirements

### Requirement: ConfirmSignup is idempotent across retries for the same external subject

The identity `ConfirmSignup` use case SHALL be safe to invoke more than
once with the same `(email, code)` pair without producing duplicate
domain rows or duplicate outbox events. Specifically:

- If the second invocation's IdP `confirm_signup(email, code)` returns
  the same `external_sub` as a previously-committed call, the use case
  SHALL detect the existing `User` aggregate and return success without
  re-inserting or re-emitting a `UserRegistered v1` event.
- If the second invocation arrives concurrently and a database
  uniqueness constraint fires on insert, the use case SHALL catch the
  `IntegrityError`, fetch the existing aggregate by `external_sub`,
  and return success without re-emitting a `UserRegistered v1` event.
- A bad-code attempt SHALL NOT leave persistent state that prevents a
  subsequent good-code attempt for the same email. Specifically, the
  local IdP `MARK_VERIFIED` SQL is allowed to run on the first
  successful code, and a SECOND successful call MUST NOT raise
  `InvalidCredentialsError` solely because `MARK_VERIFIED` already
  cleared the verification hash.

#### Scenario: Wrong code then right code on the same email succeeds

- **GIVEN** a freshly-registered local user with email
  `audit-owner@local.test` and an unexpired verification code `123456`
- **AND** the SPA has just submitted `POST /v1/auth/confirm-signup`
  with `code=000000` and received a `401 invalid_credentials`
- **WHEN** the SPA resubmits `POST /v1/auth/confirm-signup` with
  `code=123456`
- **THEN** the API SHALL respond `200 OK`
- **AND** the `users` table SHALL contain exactly one row for the user
- **AND** the outbox SHALL contain exactly one `identity.UserRegistered v1`
  event for the user

#### Scenario: Identical successful submissions are idempotent

- **GIVEN** a successful prior call to `POST /v1/auth/confirm-signup`
  for `owner1@audit.test` with `code=124613`
- **WHEN** an identical second call arrives (e.g. user smashed Enter)
- **THEN** the API SHALL respond `200 OK`
- **AND** NO additional `UserRegistered` outbox row SHALL be appended
- **AND** the response shape SHALL match the first successful response
  (same `external_sub`, same user-level fields)

#### Scenario: Bad code on an already-verified user is still rejected

- **GIVEN** a user whose `auth_local_users.email_verified` is already `true`
- **WHEN** `POST /v1/auth/confirm-signup` arrives with a `code` that
  does not match (or for which the hash has been cleared) AND the email
  is NOT verified yet
- **THEN** the API SHALL respond `401 auth.invalid_credentials`

(The idempotency exception in the first paragraph applies only to
SECOND calls on an already-verified row that match the *legitimate*
verification path. Replay of an arbitrary wrong code SHALL still 401.)
