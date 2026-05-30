## ADDED Requirements

### Requirement: Canonical RLS pattern for tenant-scoped tables

Every tenant-scoped table introduced by this change (and by sprints
04-08 that reuse the pattern) SHALL apply the canonical block:

```sql
ALTER TABLE <table> ADD COLUMN tenant_id UUID NOT NULL;
CREATE INDEX idx_<table>_tenant ON <table>(tenant_id);
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <table>
  USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

The `USING` and `WITH CHECK` clauses SHALL be the **same expression**.
The `true` flag on `current_setting` SHALL be preserved so an unset
GUC returns `NULL` rather than raising
([ADR-0002](../../../../docs/adr/0002-postgres-rls.md)).

#### Scenario: A new tenant-scoped table without the FORCE clause is rejected

- **GIVEN** a candidate migration that omits `FORCE ROW LEVEL
  SECURITY` on a tenant-scoped table
- **WHEN** the migration runs
- **THEN** the gate test `test_rls_pattern_compliance` SHALL fail
  with a message naming the offending table

### Requirement: `tenant_members` carries the special "self-OR-tenant" policy

The `tenant_members` table SHALL apply the **special** RLS policy:

```sql
CREATE POLICY tenant_members_self ON tenant_members
  USING      (user_id   = current_setting('app.current_user_id', true)::uuid
              OR tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

The `OR` branch lets an authenticated user enumerate their own
memberships before any active tenant has been picked (post-login
tenant picker). The `WITH CHECK` clause keeps the canonical
expression — a user CANNOT insert a row for a tenant other than
the active one.

#### Scenario: User reads own memberships with no active tenant

- **GIVEN** a session where `SET LOCAL app.current_user_id=<u>` is
  set and `app.tenant_id` is unset
- **WHEN** `SELECT * FROM tenant_members WHERE user_id=<u>` runs
- **THEN** the result SHALL include every row belonging to `<u>`

#### Scenario: User cannot insert a row for another tenant

- **GIVEN** a session where `app.tenant_id=<A>` is set
- **WHEN** an `INSERT INTO tenant_members(tenant_id=<B>, ...)` is
  attempted
- **THEN** the insert SHALL fail because the `WITH CHECK` clause
  evaluates `false`

### Requirement: `_RequestUnitOfWork.begin()` sets GUCs on outer entry

`bootstrap/container._RequestUnitOfWork.begin()` SHALL, on the
outer entry (when no inner session is already active), execute:

```python
await session.execute(
    text("SET LOCAL app.tenant_id = :t"),
    {"t": str(TenantContext.get()) if TenantContext.get() else
       "00000000-0000-0000-0000-000000000000"},
)
await session.execute(
    text("SET LOCAL app.current_user_id = :u"),
    {"u": str(CurrentUserContext.get().user_id)
       if CurrentUserContext.get() else
       "00000000-0000-0000-0000-000000000000"},
)
```

Both statements SHALL run BEFORE the body of `begin()` yields the
session, inside the same transaction. The reentrant inner
`begin()` branch SHALL NOT re-issue these statements (the outer
transaction's `SET LOCAL` already applies).

#### Scenario: GUCs are visible inside the transaction

- **WHEN** `_RequestUnitOfWork.begin()` is entered with a non-None
  `TenantContext`
- **THEN** `SELECT current_setting('app.tenant_id', true)` SHALL
  return the same UUID string

#### Scenario: Inner `begin()` does not re-set the GUCs

- **WHEN** a use case opens `async with uow.begin():` inside a
  handler that already opened the outer transaction
- **THEN** the inner block SHALL NOT execute additional `SET LOCAL`
  statements

### Requirement: `TenantMiddleware` validates membership before RLS sees the request

`contexts.tenants.adapters.inbound.http.middleware.TenantMiddleware`
SHALL run **after** `AuthMiddleware`. It SHALL:

1. If the route is in the unauthenticated allowlist → pass through.
2. If `CurrentUserContext.active_tenant` is `None` → leave
   `TenantContext` unset and pass through (the no-tenant allowlist
   in `AuthMiddleware` already approved the route).
3. Otherwise, open a short read-only `uow.begin()` and query
   `tenant_members` for `(user_id, claimed_tenant_id)`.
4. On miss → return 403 `tenant.not_member` problem+json.
5. On hit → `TenantContext.set(UUID(claimed_tenant_id))` and pass
   through.

The membership lookup query SHALL run with the GUCs set to the
*claimed* tenant; the special `tenant_members_self` policy lets the
query succeed via the `user_id = app.current_user_id` branch even
if the claim is forged for a tenant the user is not a member of.

#### Scenario: Forged active_tenant for a non-member returns 403

- **GIVEN** a JWT minted for user B carrying
  `custom:active_tenant=<tenant_A_id>` where B is not a member of A
- **WHEN** the request hits a tenant-scoped endpoint
- **THEN** `TenantMiddleware` SHALL respond 403 with
  `{"code": "tenant.not_member"}` and no downstream code SHALL
  execute

### Requirement: `forge_jwt` testing helper lives next to the local adapter

`contexts.identity.testing.forge_jwt(*, user_id, email,
active_tenant, secret, **claims) -> str` SHALL be a synchronous
function that produces an HS256 JWT byte-identical in claim shape
to one issued by `IdentityProviderLocal.authenticate()`. The
helper SHALL be importable from test modules but BLOCKED from
productive code via an import-linter contract that forbids any
module under `contexts/*/adapters/`,
`contexts/*/application/`, or `bootstrap/` from importing it.

#### Scenario: Helper produces a token that the middleware accepts

- **WHEN** `forge_jwt(user_id=u, email="x", active_tenant="<A>",
  secret=LOCAL_JWT_SECRET)` is decoded by `IdentityProviderLocal.verify_token`
- **THEN** the decode SHALL succeed and the returned claims SHALL
  include `custom:active_tenant="<A>"`

### Requirement: Sprint-gate test — tenant isolation via RLS

Test `tests/e2e/contexts/tenants/test_tenant_isolation.py::test_tenant_isolation_via_rls`
SHALL exercise:

1. Create two users A and B (via the identity adapter).
2. Each creates a tenant (`tenant_A`, `tenant_B`).
3. A invites a third email `x@test.dev` to `tenant_A`.
4. With B authenticated against `tenant_B`, a `GET
   /v1/tenants/{tenant_A_id}/invitations` SHALL return HTTP 404.
5. With a `forge_jwt` for B claiming `custom:active_tenant=<tenant_A_id>`,
   a `GET /v1/tenants/{tenant_A_id}/members` SHALL return HTTP 403
   with `code="tenant.not_member"`.

Steps 4 and 5 together demonstrate **defence in depth**: RLS hides
data (step 4), middleware rejects forged claims (step 5).

#### Scenario: Full flow passes against the testcontainer

- **WHEN** the e2e test runs against `make test`
- **THEN** every assertion SHALL pass and the test SHALL be marked
  as a sprint gate (failing the test blocks merge)
