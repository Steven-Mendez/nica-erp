## ADDED Requirements

### Requirement: Backend gap — per-user permission overrides (specified, NOT implemented in this change)

The backend SHALL eventually expose per-user permission overrides
so the SPA can grant or revoke an individual permission for a
single member without changing their role. This change does NOT
implement the gap; it captures the contract the follow-up sprint
MUST honour so the work is schedulable from the spec alone.

The sprint 03 RBAC catalog today
(`apps/api/src/shared_kernel/permissions/catalog.py`) defines
permissions per **role**, not per **member**. The
`Empresa → Usuarios` page in this change surfaces role changes
only.

The follow-up sprint SHALL deliver:

- A new table `tenant_member_permissions(tenant_id, user_id,
  permission_code, granted, created_at)`, PK
  `(tenant_id, user_id, permission_code)`, RLS policy matching
  the canonical `tenant_isolation` pattern, FK to `tenant_members`
  on `(tenant_id, user_id)` with `ON DELETE CASCADE`.
- A new permission code `members:update-permissions` seeded into
  the catalog for `owner` and `admin` roles.
- Endpoints:
  - `GET /v1/tenants/{tenant_id}/members/{user_id}/permissions`
    → 200 `{ effective: [code, …], role_grants: [code, …],
    overrides: [{code, granted}, …] }`. Gated by `members:read`.
  - `PUT /v1/tenants/{tenant_id}/members/{user_id}/permissions`
    body `{ grants: [{code: string, granted: bool}], …}` → 204.
    Gated by `members:update-permissions`. Validates each `code`
    against the catalog (rejecting unknown codes), rejects
    attempts to flip permissions for the owner (single-owner
    invariant), and emits a `MemberPermissionsChanged v1` outbox
    event.
- Updated `Actor.permissions` resolver in
  `apps/api/src/bootstrap/dependencies.py`:
  - Start from `DEFAULT_ROLE_PERMISSIONS[role]`.
  - Apply overrides: `granted=true` codes are added, `granted=false`
    codes are removed.
  - The resolver MUST keep its 60-second TTL cache; cache key
    SHALL include the override row's `created_at` so invalidation
    happens on the next mutation.

#### Scenario: Owner is immune to permission overrides

- **GIVEN** an admin tries to flip `tenant:read` to `false` for
  the empresa owner
- **WHEN** they send
  `PUT /v1/tenants/{id}/members/{owner_user_id}/permissions`
- **THEN** the API responds 403 `members.cannot_override_owner`
  (or 422 with the same code) and the owner's effective set is
  unchanged

#### Scenario: Override unions with the role catalog

- **GIVEN** a `salesperson` whose role catalog is
  `{tenant:read}` and the operator grants them
  `{code: "members:read", granted: true}`
- **WHEN** `Actor.permissions` is resolved for that member
- **THEN** the effective set is `{tenant:read, members:read}`

### Requirement: Backend gap — `POST /v1/invitations/accept` must set `app.tenant_id` (already tracked)

The accept endpoint `POST /v1/invitations/accept` SHALL set
`set_config('app.tenant_id', '<verified token tenant_id>', true)`
on its session before reading the `invitations` row, so the
per-tenant RLS policy passes during invitee acceptance. The fix
is tracked under [[test-backfill-and-e2e-tooling]] §3.2 and MUST
ship before the invitee-side accept flow can succeed at runtime.

The fix is owned by the test-backfill change; surfaced here for
completeness because the `Empresa → Usuarios` page lists pending
invitations that a future invitee will accept. The owner-facing
view in this change does not depend on the fix (the owner's
session has `app.tenant_id` set by the tenant middleware).

#### Scenario: Invitee accepts an invitation after the GUC fix lands

- **GIVEN** the GUC fix has landed and the invitee follows the
  link from their invitation email
- **WHEN** the invitee POSTs to `/v1/invitations/accept`
- **THEN** the AcceptInvitation use case sets
  `app.tenant_id` to the verified token's tenant claim, the
  RLS-protected SELECT succeeds, and the response carries the new
  membership's `tenant_id` and `role`
