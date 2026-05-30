## ADDED Requirements

### Requirement: `IdentityProvider` outbound port

The `IdentityProvider` Protocol SHALL be runtime-checkable and SHALL
declare the eleven methods listed in
[`docs/06-security-model.md` §Port methods](../../../../docs/06-security-model.md#port-methods):
`register`, `authenticate`, `verify_token`, `refresh`, `confirm_signup`,
`resend_confirmation`, `forgot_password`, `confirm_forgot_password`,
`change_password`, `global_signout`, `update_active_tenant`. Each
method SHALL be `async`. The return shape MUST be the same dataclass
`Identity(sub, email, access_token, refresh_token, id_token, claims)`
regardless of which adapter answers. The port SHALL live in
`contexts.identity.application.ports.outbound.identity_provider`.

#### Scenario: Use cases depend only on the port

- **WHEN** static analysis grep is applied to
  `contexts/identity/application/use_cases/*.py`
- **THEN** the only identity-related imports SHALL be from
  `contexts.identity.application.ports.outbound.identity_provider` (no
  imports of either adapter module)

### Requirement: `UserRepository` outbound port

The `UserRepository` Protocol SHALL be runtime-checkable and SHALL
expose `async get_by_id(user_id: UUID) -> User | None`,
`async get_by_external_sub(external_sub: str) -> User | None`,
`async add(user: User) -> None`, and `async update(user: User) -> None`.
Implementations SHALL persist using the active `UnitOfWork`'s session —
no implementation may open its own connection. The port SHALL live in
`contexts.identity.application.ports.outbound.user_repository`.

#### Scenario: `add` and `get_by_external_sub` round-trip

- **WHEN** a `User` aggregate is added via `add()` and the same
  `external_sub` is looked up via `get_by_external_sub()`
- **THEN** the returned aggregate SHALL equal the original under
  identity-based equality

### Requirement: `EmailSender` outbound port

The `EmailSender` Protocol SHALL be runtime-checkable and SHALL declare
exactly one method: `async send(*, to: str, subject: str, html: str,
text: str) -> None`. The caller SHALL provide both an HTML and a
plain-text body so the SMTP adapter can attach them as a multipart
message and the SES adapter can forward them verbatim. The port MUST
NOT define a method for "verify sender" or "list verified identities"
— those are operator concerns, not application concerns. The port SHALL
live in `contexts.identity.application.ports.outbound.email_sender`.

#### Scenario: Adapters share the same signature

- **WHEN** `EmailSenderSmtp` and `EmailSenderSes` are inspected with
  `inspect.signature(...).parameters`
- **THEN** both signatures SHALL declare the same keyword-only
  parameters `to`, `subject`, `html`, `text`

### Requirement: Inbound use cases

The package `contexts.identity.application.use_cases` SHALL ship the
eleven use cases listed in
[`docs/sprints/02-identity-and-rbac.md`](../../../../docs/sprints/02-identity-and-rbac.md):
`register_user`, `confirm_signup`, `resend_code`, `authenticate`,
`refresh_token`, `change_password`, `forgot_password`,
`reset_password`, `logout`, `get_me`, `update_profile`. Each use case
SHALL be a keyword-only dataclass whose initialiser takes its outbound
ports explicitly (no service locator, no implicit globals) and SHALL
expose a single `async execute(...)` method that opens a
`UnitOfWork.begin()` exactly once.

#### Scenario: `register_user.execute` opens one transaction

- **WHEN** `register_user.execute(email=..., password=...)` is called
  with a mocked `UnitOfWork`
- **THEN** the mock's `begin().__aenter__` SHALL be invoked exactly once

### Requirement: `confirm_signup` writes `UserRegistered` to the outbox atomically

`confirm_signup.execute()` SHALL, in a single `UnitOfWork.begin()`:
(1) call `IdentityProvider.confirm_signup(...)` and obtain the
`external_sub`; (2) persist the `User` aggregate through
`UserRepository.add(...)`; (3) emit `identity.UserRegistered v1` via
`OutboxWriter.append(...)` with `tenant_id =
'00000000-0000-0000-0000-000000000000'` (the system-global sentinel)
and payload `{user_id, email, registered_at}`. The transaction SHALL
commit only when all three steps succeed.

#### Scenario: Failure in the outbox write aborts the user persistence

- **WHEN** `OutboxWriter.append` raises during `confirm_signup`
- **THEN** the transaction SHALL roll back and the `User` SHALL NOT be
  visible in a fresh `get_by_external_sub` query

#### Scenario: Outbox row carries the system-global tenant sentinel

- **WHEN** a successful `confirm_signup` completes
- **THEN** the `outbox` row for the emitted event SHALL have
  `tenant_id = '00000000-0000-0000-0000-000000000000'` and
  `event_type = 'identity.UserRegistered'`

### Requirement: `register_user` and `forgot_password` resist email enumeration

`register_user.execute(...)` and `forgot_password.execute(...)` SHALL
return the same response shape and HTTP-mappable outcome regardless of
whether the supplied email already corresponds to an account. The
adapters SHALL still perform whatever side effect is correct (Cognito's
`SignUp` returns `UsernameExistsException`; the local adapter silently
no-ops for an existing verified user) but the use case SHALL collapse
those branches into a single success response.

#### Scenario: Existing-email register returns the same shape as new-email register

- **WHEN** `register_user.execute(email="taken@x.io", password=valid)`
  is called for an email that already exists, and again with a fresh
  email
- **THEN** both invocations SHALL return responses that are
  byte-indistinguishable in their HTTP-visible fields

### Requirement: Authenticate maps lockout, expiry, and bad credentials to distinct errors

`authenticate.execute(...)` SHALL raise typed errors that the HTTP
adapter maps to RFC-7807 problem details with stable codes:
`auth.invalid_credentials` (401), `auth.lockout_active` (401 with a
`retry_after_seconds` extension), and `auth.signup_email_not_confirmed`
(401 with a `code=auth.signup_email_not_confirmed` extension). Token
verification errors during a `verify_token` call SHALL map to
`auth.token_expired` (401) when `exp` is in the past, and to
`auth.invalid_credentials` otherwise.

#### Scenario: Five failed attempts yield a lockout error

- **WHEN** the local adapter has recorded five failed attempts within
  the configured window and a sixth attempt arrives
- **THEN** `authenticate.execute(...)` SHALL raise the lockout error
  type and the HTTP layer SHALL emit a 401 with `code =
  "auth.lockout_active"` and an extension `retry_after_seconds`

### Requirement: `logout` invalidates the server-side session via `global_signout`

The `logout` use case SHALL accept the caller's
`CurrentUserContext` (already populated by the auth middleware from
the access token's `sub`) and SHALL invoke
`IdentityProvider.global_signout(external_sub=...)` exactly once. The
use case SHALL succeed (return `None`) even if the underlying
`global_signout` call reports that the user has no active session —
logout MUST be idempotent so a double-click or replay does not surface
an error to the SPA. Access tokens already issued REMAIN valid until
their `exp` per
[`docs/06-security-model.md` §Refresh and revocation](../../../../docs/06-security-model.md#refresh-and-revocation);
the use case does not attempt to short-circuit them.

#### Scenario: Logout calls global_signout exactly once

- **WHEN** `logout.execute()` is awaited with a mocked
  `IdentityProvider` and a populated `CurrentUserContext`
- **THEN** `IdentityProvider.global_signout` SHALL be called exactly
  once with `external_sub` matching the context's `sub`

#### Scenario: Logout is idempotent

- **WHEN** `logout.execute()` is awaited twice in succession with the
  same `CurrentUserContext`
- **THEN** both invocations SHALL return `None` and neither SHALL
  raise

### Requirement: `forgot_password` adapters SHALL swallow the unknown-email branch

Every `IdentityProvider` adapter SHALL silently swallow the
"user does not exist" branch of its `forgot_password` call (Cognito's
`UserNotFoundException`; the local adapter's "email not in
`auth_local_users`" branch) and return a result whose shape matches
the real-account branch. The use case MUST NOT need to inspect
adapter-side exceptions to keep the HTTP response uniform — that is
the contract that makes `forgot_password.execute(...)`'s
enumeration-resistance achievable without leaking adapter internals
into the application layer.

#### Scenario: Use case observes a uniform adapter response

- **WHEN** `forgot_password.execute(email=...)` is invoked for an
  email that does not exist in the IdP
- **THEN** the use case SHALL NOT observe any "user not found"
  exception from the port; the call SHALL complete and the HTTP layer
  SHALL emit the same response shape as a real-account reset
