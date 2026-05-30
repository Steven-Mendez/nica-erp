## ADDED Requirements

### Requirement: Outbound ports isolate persistence and token minting

`contexts.tenants.application.ports.outbound` SHALL declare:

- `TenantRepository`: `async get(id) -> Tenant | None`, `async add(t)`,
  `async update(t)`, `async list_for_user(user_id) -> list[Tenant]`.
- `MembershipRepository`: `async get(id) -> Membership | None`,
  `async add(m)`, `async update(m)`,
  `async list_by_tenant(tenant_id) -> list[Membership]`,
  `async find(user_id, tenant_id) -> Membership | None`.
- `InvitationRepository`: `async add(i)`, `async update(i)`,
  `async get_by_token_hash(h) -> Invitation | None`,
  `async list_by_tenant(tenant_id) -> list[Invitation]`.
- `InvitationTokenGenerator`: `mint(*, tenant_id, email,
  proposed_role) -> tuple[str, str, datetime]` (plaintext token,
  SHA-256 hash, `expires_at`), `verify(*, token) -> dict[str, Any]`
  (raises on invalid signature/expiry).

All four protocols SHALL be `@runtime_checkable` Protocols.

#### Scenario: `TenantRepository` satisfies the protocol

- **WHEN** a concrete `TenantRepository` implementation is checked
  against the Protocol via `isinstance(repo, TenantRepository)`
- **THEN** the check SHALL return `True`

### Requirement: `CreateTenant` creates tenant + owner membership atomically

`CreateTenant.execute(*, actor_user_id, name, ruc, regime,
municipality, authorization_dgi, fiscal_address, is_withholder)`
SHALL, within a single `UnitOfWork.begin()`:

1. Construct a `Tenant` via `Tenant.register(...)` (recording
   `TenantCreated v1`).
2. Construct a `Membership` via `Membership.create_owner(...)` for
   `actor_user_id`.
3. Persist both via the repositories.
4. Append `tenants.TenantCreated v1` to the outbox with
   `tenant_id=<the new id>` and the canonical event payload.

A failure at any step SHALL roll back the entire UoW. The use case
SHALL NOT call `IdentityProvider.update_active_tenant` — the SPA is
expected to call `POST /v1/tenants/{id}/switch` after creation.

#### Scenario: Successful creation persists both rows

- **WHEN** `CreateTenant.execute(...)` succeeds
- **THEN** the database SHALL contain exactly one `tenants` row and
  exactly one `tenant_members` row with `role='owner'` for the
  same `(user_id, tenant_id)` pair

#### Scenario: Outbox row uses the new tenant id

- **WHEN** `CreateTenant.execute(...)` succeeds
- **THEN** the matching `outbox` row SHALL have `tenant_id` equal to
  the new tenant's id (not the system-global sentinel)

### Requirement: `InviteMember` rejects owner role and mints a signed token

`InviteMember.execute(*, actor, tenant_id, email, proposed_role)`
SHALL reject `proposed_role == Role.OWNER` with
`OwnerRoleNotAllowedHereError`. For any other role it SHALL:

1. Call `InvitationTokenGenerator.mint(...)`.
2. Persist an `Invitation` with the token hash, `status='pending'`,
   `expires_at` from the generator.
3. Emit `tenants.MemberInvited v1` to the outbox.
4. Call `EmailSender.send(...)` with the plaintext URL embedding
   the token.

Step 4 is synchronous; a failure SHALL surface as the use case
exception (HTTP 5xx). The use case SHALL match the sprint 02
signup-verification synchronous pattern.

#### Scenario: Owner role rejected

- **WHEN** `InviteMember.execute(actor, tenant_id, "x@y.io", Role.OWNER)`
  is called
- **THEN** `OwnerRoleNotAllowedHereError` SHALL be raised before any
  IO

#### Scenario: Token hash persisted, plaintext sent via email

- **WHEN** `InviteMember.execute(...)` succeeds
- **THEN** the `invitations.token_hash` SHALL equal the
  hexadecimal SHA-256 of the plaintext token, and the
  `EmailSender.send(...)` call SHALL have received a URL string
  containing the plaintext token

### Requirement: `AcceptInvitation` is public and atomic

`AcceptInvitation.execute(*, token)` SHALL run without an active
tenant (it is called via the unauthenticated allowlist route). It
SHALL:

1. Call `InvitationTokenGenerator.verify(token=token)` to validate
   the signature and expiry; raise `InvitationExpiredError` on
   expiry, `InvitationInvalidError` on signature failure.
2. Hash the token (SHA-256) and look up the `Invitation` by hash;
   raise `InvitationNotFoundError` on miss.
3. Call `Invitation.accept(now)` (which itself raises if the
   invitation is already accepted/cancelled).
4. Insert a `Membership` for `(user_id_from_jwt_or_signup,
   tenant_id_from_invitation)` with the proposed role.
5. Persist the invitation update.
6. Emit `tenants.MemberJoined v1` to the outbox with
   `tenant_id=<invitation.tenant_id>` (NOT the system-global
   sentinel).

If the accepting user is not yet authenticated (no
`CurrentUserContext`), the use case SHALL reject with
`AuthenticationRequiredError`. The SPA's flow ensures the user is
logged in before reaching `/invitations/$token/accept`.

#### Scenario: Acceptance flips invitation and inserts membership

- **WHEN** a pending invitation is accepted by an authenticated user
- **THEN** the `invitations.status` SHALL be `'accepted'` AND a
  `tenant_members` row SHALL exist with `(user_id, tenant_id, role)`
  matching the invitation

### Requirement: `SwitchActiveTenant` calls the IdP and returns a fresh Identity

`SwitchActiveTenant.execute(*, actor_user_id, external_sub,
target_tenant_id, refresh_token)` SHALL:

1. Look up `(actor_user_id, target_tenant_id)` in
   `tenant_members`; raise `NotAMemberError` on miss.
2. Call `IdentityProvider.update_active_tenant(external_sub,
   str(target_tenant_id))`.
3. Call `IdentityProvider.refresh(refresh_token=refresh_token)` to
   obtain a fresh `Identity` with the updated claim.
4. Return the `Identity`.

A failure at step 2 SHALL NOT call step 3 (no fresh tokens minted
against a stale attribute). A failure at step 3 leaves the IdP-side
attribute updated; the next login picks up the new claim.

#### Scenario: Membership absent → 403

- **WHEN** the actor is not a member of `target_tenant_id`
- **THEN** `NotAMemberError` SHALL be raised; neither IdP method
  SHALL be called

#### Scenario: Fresh Identity carries new claim

- **WHEN** the switch succeeds against
  `IdentityProviderLocal.update_active_tenant` + `refresh`
- **THEN** the returned `Identity.claims["custom:active_tenant"]`
  SHALL equal `str(target_tenant_id)`

### Requirement: `RemoveMember` rejects the owner role

`RemoveMember.execute(*, actor, tenant_id, target_user_id)` SHALL,
within a UoW:

1. Look up the target membership; raise `NotAMemberError` on miss.
2. If the target's role is `Role.OWNER`, raise
   `CannotRemoveOwnerError`.
3. Otherwise flip `status='removed'`, set `removed_at=now`,
   persist the membership.
4. Emit `tenants.MemberRemoved v1` to the outbox.

#### Scenario: Removing an admin succeeds

- **WHEN** `RemoveMember.execute(...)` targets a member with role
  `admin`
- **THEN** the membership row SHALL have `status='removed'` and
  a `MemberRemoved` event SHALL be in the outbox

#### Scenario: Removing the owner is rejected

- **WHEN** `RemoveMember.execute(...)` targets the tenant owner
- **THEN** `CannotRemoveOwnerError` SHALL be raised and no
  `outbox` row SHALL be written

### Requirement: `UpdateTenant` cannot change RUC and refreshes timestamp

`UpdateTenant.execute(*, actor, tenant_id, **fields)` SHALL:

1. Load the tenant; raise `TenantNotFoundError` on miss (RLS hides
   foreign tenants, so this is the same as 404).
2. Call `Tenant.update_fiscal(**fields, now=now)` — passing `ruc=`
   raises `TypeError` per the domain spec.
3. Persist.

The use case SHALL NOT emit a `TenantUpdated` event in MVP — sprint
03's outbox payload set is limited to the six listed events.

#### Scenario: Updating fiscal address persists

- **WHEN** `UpdateTenant.execute(tenant_id=t, fiscal_address="X")` is
  called by an `admin`
- **THEN** the row SHALL reflect the new address and a fresh
  `updated_at`

### Requirement: Use cases compose with the request UoW

Every use case in this capability SHALL accept its `uow` and outbox
writer at construction time and SHALL open `async with uow.begin():`
itself. The HTTP-level reentrant UoW (sprint 02's `_RequestUnitOfWork`)
guarantees the inner `begin()` is a no-op when an outer transaction
is already open, so use cases compose without double-commits.

#### Scenario: Inner `begin()` is reentrant

- **WHEN** a use case is called from inside an HTTP handler that
  already opened the outer transaction
- **THEN** the use case's `async with self.uow.begin():` SHALL
  yield the same session and SHALL NOT start a nested SAVEPOINT
