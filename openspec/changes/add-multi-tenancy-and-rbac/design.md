## Context

This change stacks on top of sprint 02
([`add-identity-context`](../add-identity-context/proposal.md)). The
architectural envelope is fixed by:

- [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md)
  — the sprint contract; this change MUST NOT exceed it (and MUST
  match its four sprint-gate tests).
- [`docs/05-multi-tenancy.md`](../../../docs/05-multi-tenancy.md) —
  the canonical RLS pattern, GUC names, special-case policies, and
  the `current_setting(..., true)::uuid` idiom.
- [`docs/06-security-model.md`](../../../docs/06-security-model.md) —
  the RBAC matrix per role and the `Actor` materialisation contract.
- [`docs/08-api-conventions.md`](../../../docs/08-api-conventions.md)
  — RFC-7807 problem shape (`type=missing-permission`,
  extension `missing: [...]`) and the 403-vs-404 disambiguation rule.
- [`docs/09-frontend.md`](../../../docs/09-frontend.md) — feature
  slice rules, no cross-feature imports, OpenAPI-typed client.
- [ADR-0002](../../../docs/adr/0002-postgres-rls.md) — pool + RLS,
  GUC tenancy, special policy for `tenant_members`.
- [ADR-0022](../../../docs/adr/0022-rbac-model.md) — five fixed
  roles, granular `<resource>:<action>` permissions, hybrid
  ownership (introduced here only via the `scope` column; the
  filter mixin lands in sprint 04 with the first owned aggregate).
- [ADR-0026](../../../docs/adr/0026-tenant-lifecycle.md) —
  `tenants.status` lifecycle; this change implements only the
  default `active` state. Transitions are out of scope.

## Goals / Non-Goals

**Goals**

- A contributor with a fresh checkout can sign up two users in two
  browsers, each creates a tenant, A invites B, B accepts, B switches
  to A's tenant, sees A's data. The cross-tenant peek (B → tenant A
  while authenticated as tenant B) returns 404, and a `forge_jwt`
  attack returns 403 — both as automated gate tests.
- Every new endpoint exposes its required permission via OpenAPI
  (so the SPA can render disabled buttons) AND enforces it via
  `Depends(require(...))` (so the SPA cannot bypass by URL).
- The canonical RLS pattern (`USING` + `WITH CHECK` same expression,
  index on `tenant_id`, `FORCE ROW LEVEL SECURITY`) is a copy-paste
  template documented in this design + the `multi-tenancy-rls`
  spec. Sprints 04-08 will copy it per table without re-deriving.
- The permission catalog (`shared_kernel/permissions/catalog.py`) is
  the single source of truth; the DB is a materialised view of it
  applied via migration. A test enumerates `role_permissions` and
  fails on any divergence.

**Non-Goals**

- Tenant lifecycle transitions beyond default `active`. `provisioning
  → active` is collapsed to a constructor default in sprint 03;
  `suspended` and `purged` ship as operator runbooks
  ([ADR-0026](../../../docs/adr/0026-tenant-lifecycle.md)).
- Hybrid-ownership repository mixin (`OwnedAggregateRepository`).
  Lands in sprint 04 alongside `Invoice` — premature here because
  no aggregate has a `created_by_user_id` yet.
- Cross-tenant analytics, `BYPASSRLS` DB role, super-admin tooling.
- The async notifications worker — sprint 08 consumes
  `MemberInvited` from the outbox.
- AWS deploy. Account in verification. The Terraform side of the
  sprint is already covered by sprint 02 (Cognito + IAM); no new
  modules are introduced.

## Decisions

### Sprint 02's `_RequestUnitOfWork` becomes the GUC-setting injection point

The reentrant `_RequestUnitOfWork` lives in `bootstrap/container.py`
([sprint 02 closure](../../../docs/sprints/02-identity-and-rbac.md)).
This change extends it: on the **outer** `begin()` (when
`self._session is None`), after the parent opens the transaction and
before yielding, it executes:

```python
await session.execute(
    text("SET LOCAL app.tenant_id = :t"),
    {"t": str(TenantContext.get() or "00000000-0000-0000-0000-000000000000")},
)
await session.execute(
    text("SET LOCAL app.current_user_id = :u"),
    {"u": str(current_user_id or "00000000-0000-0000-0000-000000000000")},
)
```

The sentinel UUID is the same one sprint 02 uses for tenantless
outbox events; here it represents "no tenant active" — the
canonical RLS policies use `current_setting('app.tenant_id', true)::uuid`,
and with `true` an unset GUC returns `NULL`, but the GUC is **set**
in this branch (to a zero UUID that no real row will match). That
keeps the SQL parser path uniform and makes "no rows returned because
no tenant active" a deterministic outcome rather than an error.

The reentrant inner `begin()` does **not** re-execute these
`SET LOCAL` statements — they already apply to the outer
transaction. This matches the sprint 02 invariant
(`feedback_plan_before_implement` memory: the reentrant UoW affects
non-HTTP entry points calling identity use cases too).

Alternative considered: set the GUCs from `TenantMiddleware` directly
on a session pulled from the factory. Rejected — the middleware has
no transaction yet, and `SET LOCAL` outside a transaction is a
no-op in `psycopg`. The UoW is the only place where "we are inside
a transaction" is guaranteed.

### `TenantMiddleware` is order-coupled to `AuthMiddleware`

`AuthMiddleware` populates `CurrentUserContext` with `active_tenant`
extracted from the JWT. `TenantMiddleware` reads it. So
`AuthMiddleware` MUST run **before** `TenantMiddleware`. Starlette
runs middleware in reverse order of addition (last-added is
outermost), so the registration in `bootstrap/api.py` is:

```python
app.add_middleware(TenantMiddleware, ...)   # innermost
app.add_middleware(AuthMiddleware, ...)     # outer
app.add_middleware(CORSMiddleware, ...)     # outermost
```

That order also means a 401 from `AuthMiddleware` never reaches
`TenantMiddleware`, and a CORS preflight never reaches either —
both desirable.

Alternative considered: fold the membership check into
`AuthMiddleware`. Rejected — the membership lookup hits the database
(`tenant_members`), and `AuthMiddleware` is intentionally
DB-free (it only calls `IdentityProvider.verify_token`, which both
adapters keep DB-free). Splitting preserves that.

### Membership lookup runs **inside** a UoW, before `current_actor`

`TenantMiddleware` validates `tenant_members` with its own short
read-only `uow.begin()` block. This SETs the GUCs (via the
hook above) using the *claimed* tenant from the JWT. The query
goes through the `tenant_members_self` RLS policy: the `OR`
branch on `user_id = app.current_user_id` lets the user see their
own membership rows even when the active tenant in the JWT is forged
or stale. If no `(user_id, tenant_id)` row exists, the middleware
returns 403 `tenant.not_member`.

Trade-off: every authenticated request pays one extra round trip.
The query is a single indexed lookup on a tiny table — sub-millisecond
in practice. We accept the cost in exchange for the defence-in-depth:
even if the JWT signing key leaks, a forged `custom:active_tenant`
cannot grant access to a tenant the user is not a member of.

### `current_actor` materialises `Actor` once per request via DI

`bootstrap/dependencies.py.current_actor` is a FastAPI dependency
that reads `CurrentUserContext` + `TenantContext`, queries
`tenant_members` for the role, queries `role_permissions` for the
permission set (through the TTL-60s cache), and returns an
`Actor(user_id, tenant_id, role, permissions)`. `require(*codes)`
consumes the same `Actor`. FastAPI's DI graph deduplicates within
a request, so the cost is exactly one membership query +
(potentially zero) cache lookups per request, regardless of how
many `require(...)` dependencies a route declares.

Edge case: routes in `NO_TENANT_REQUIRED` (the whitelisted set —
`GET /v1/me`, `POST /v1/tenants`, etc.) skip `current_actor`. They
also don't use `require(...)`. If a future route needs an actor
without a tenant (unlikely), the dependency yields an `Actor` with
`tenant_id=None`, `role=None`, `permissions=frozenset()` and
`require(...)` 403s with the missing codes.

### Permission TTL cache: process-local dict, not LRU

The cache is a module-level `dict[str, tuple[float, frozenset[str]]]`
guarded by an `asyncio.Lock` for the **fetch** path (so concurrent
cache misses for the same role do not stampede the DB). The TTL is
60 s, which is the contract surfaced in [ADR-0022](../../../docs/adr/0022-rbac-model.md).
We deliberately do not use `functools.lru_cache` — it has no TTL
semantics and the cache is tiny (≤ 5 roles).

Alternative considered: invalidate on `role_permissions` write. Rejected —
the only write site is the migration (per ADR-0022). A reseed via
migration triggers a redeploy; the cache is fresh per process.

### 403 vs 404 disambiguation lives in the use case, not the router

[ADR-0022](../../../docs/adr/0022-rbac-model.md) states 404 is for
"does not exist (or invisible by RLS)" and 403 for "exists but
forbidden". The router relies on:

- `Depends(require(...))` → 403 before the use case runs if the
  caller lacks the permission. This is the **permission** check.
- The use case's repository call returns `None` if RLS hides the row
  → the use case raises `NotFoundError` → router renders 404. This is
  the **existence** check.

The gate test `test_403_vs_404` exercises both. The trade-off is
mild leakage: a permitted caller can distinguish "does not exist"
(404) from "exists but I lack access" (403). For tenant-scoped
resources visible by RLS this distinction is irrelevant (RLS hides
everything outside the tenant). For ownership-hybrid resources
(sprint 04+) this is the canonical posture per ADR-0022.

### Invitation tokens: HS256 JWT signed with `LOCAL_JWT_SECRET`

Reuse the local-IdP secret. The token carries `{tenant_id, email,
proposed_role, exp}` and is signed HS256. The **hash** of the
encoded token is stored in `invitations.token_hash` (SHA-256). The
plaintext travels only via email; the DB never holds it. On accept,
the API verifies the signature, looks up the hash, checks `status='pending'`
and `expires_at > now()`, and atomically:

1. Inserts a `tenant_members` row with the proposed role.
2. Updates `invitations.status='accepted'`.
3. Emits `tenants.MemberJoined v1` to the outbox.

Alternative considered: opaque random tokens stored only in
`token_hash`. Rejected — JWTs let the API reject obviously-forged
tokens before the DB query, and the email-carrying-payload property
is useful for the SPA's `/invitations/$token/accept` route (it can
pre-render the tenant name from the unauthenticated decode).

Caveat: tokens longer than ~32 bytes when base64-encoded. Acceptable
for email links — operators copy/paste.

### Single owner constraint: partial unique index, not CHECK

The sprint 03 doc and ADR-0022 require exactly one owner per tenant.
We enforce it with `CREATE UNIQUE INDEX uq_tenant_members_owner ON
tenant_members(tenant_id) WHERE role='owner' AND status='active'`.

Alternative considered: a CHECK constraint or a trigger. Rejected —
the partial index is the standard Postgres idiom, expresses
"at most one active owner per tenant" exactly, and is enforced by
the planner at insert time without extra code.

A `RemoveMember(role='owner')` use case explicitly fails
("cannot remove the owner") — the partial index would also reject
the operation, but failing in the use case yields a clearer
`tenants.cannot_remove_owner` 409 instead of a raw
`IntegrityError`.

### `SwitchActiveTenant` returns a fresh `Identity`

The SPA needs the new JWT with `custom:active_tenant=<new>` to make
any further request after the switch. The endpoint:

1. Verifies membership (`Depends(require(...))` is not the right
   gate here — the user *might* have no role in the target tenant
   yet… actually a member always has a role, so we just check
   the membership row exists for `(user_id, target_tenant_id)`).
2. Calls `IdentityProvider.update_active_tenant(external_sub, tenant_id)`.
3. Mints a fresh `Identity` by calling
   `IdentityProvider.refresh(refresh_token=...)` or, in the local
   adapter, by directly minting tokens with the new claim. The
   Cognito case requires the SPA's refresh token; Local mints fresh
   without needing one.

Trade-off: the SPA must send its refresh token in the body of
`POST /v1/tenants/{id}/switch` so the API can call Cognito's
`InitiateAuth(REFRESH_TOKEN_AUTH)` to obtain new tokens with the
updated attribute. The endpoint accepts `{refresh_token: string}`
in the body. Local adapter ignores the field. This is consistent
with [`docs/06-security-model.md` §Refresh and revocation](../../../docs/06-security-model.md#refresh-and-revocation).

Alternative considered: just call `update_active_tenant` and let
the SPA refresh on its own. Rejected — that's a two-round-trip
flow vs. one, and the SPA already holds the refresh token; passing
it to the API is no leakage.

### `forge_jwt` helper lives in `contexts/identity/testing.py`

Sprint 02 already imports the HS256 encoder. Sprint 03 needs a way
to construct a JWT for a user whose `custom:active_tenant` does
not match a real membership (the isolation gate test). The helper
re-uses the same `jwt.encode(...)` call the local adapter uses,
so its claim shape is byte-identical to a real token. It is
**blocked** from productive code by an import-linter contract
(no module under `contexts/*/adapters/` or `contexts/*/application/`
may import from `contexts.identity.testing`).

Alternative considered: a separate forge utility under
`tests/_helpers/`. Rejected — the encoder logic would diverge from
the local adapter over time. Keeping the helper next to the
adapter (in a `testing.py` sibling) keeps them in sync.

### `GET /v1/me` extension is additive, not a v2 bump

Sprint 02 shipped `/v1/me` returning the user profile. Sprint 03
adds `role: string | null` and `permissions: string[]`. This is an
**additive** change — no field is removed or renamed, so no `/v2`
is needed ([ADR-0027](../../../docs/adr/0027-api-versioning.md)).
Old SPA builds that ignore the new fields continue to work; new SPA
builds gate UI on `permissions`. The OpenAPI schema regenerates and
the typed `paths` get the new fields with TypeScript-optional
semantics (`role?` resolves at runtime to `null`, not undefined,
when no tenant is active — the schema documents this explicitly).

### Catalog seed runs in the migration, not in app code

The migration imports `shared_kernel.permissions.catalog` and does
`INSERT ... ON CONFLICT DO NOTHING`. Sprints 04-08 will *extend*
the catalog (`CATALOG_PERMISSIONS`, `SALES_PERMISSIONS`, etc.) and
add their own seed blocks in their migrations. This pattern lets
each sprint own its permissions without coupling.

Trade-off: a migration that imports application code is not pure
schema. We accept it because the catalog is the single source of
truth and the alternative (duplicating it in raw SQL) drifts.
Alembic's `op.bulk_insert` makes the call site clean. The test
`test_role_permission_matrix` enumerates the DB and compares to
`DEFAULT_ROLE_PERMISSIONS` — any drift fails CI.

### Tenant creation also creates the owner membership

`CreateTenant` is a single use case that, in one UoW:

1. Inserts the tenant row.
2. Inserts the owner `tenant_members` row for the calling user.
3. Emits `TenantCreated v1` to the outbox.

The partial-unique index guarantees no double-owner. The "no active
tenant" allowlist lets the call go through without a tenant set;
the use case does not require the tenant middleware to have run
(it has no active tenant yet — it is creating one).

After `CreateTenant` returns, the SPA must call
`POST /v1/tenants/{id}/switch` to obtain a JWT with the new
`custom:active_tenant` so further requests succeed. Documented in
the sprint doc.

## Risks / Trade-offs

- **Risk**: A migration that imports application code (the catalog
  seed) gets out of sync with the Python module if a contributor
  edits one and not the other. **Mitigation**: `test_role_permission_matrix`
  fails on any divergence; the migration explicitly imports
  `shared_kernel.permissions.catalog` rather than duplicating
  literals.

- **Risk**: `SET LOCAL` is missed on a code path that opens a raw
  session (skipping the UoW). **Mitigation**: the RLS policies use
  `current_setting('app.tenant_id', true)::uuid` — `true` makes
  the GUC return `NULL` when unset, and the comparison
  `tenant_id = NULL::uuid` is `UNKNOWN`, so every row is filtered.
  The canonical bug signal "zero rows for every tenant" is the
  loud failure mode; the sprint-gate isolation test would catch it.

- **Risk**: A forged JWT with a real `custom:active_tenant` lands
  in the API. **Mitigation**: `TenantMiddleware` validates membership
  before `SET LOCAL`. The isolation gate test forges such a JWT
  for user B against tenant A and asserts 403.

- **Risk**: Cache TTL of 60 s means a freshly-seeded permission
  takes up to a minute to propagate per process. **Mitigation**:
  acceptable per [ADR-0022](../../../docs/adr/0022-rbac-model.md);
  the only mutation site is the migration, which triggers a
  redeploy, which restarts processes — the cache is fresh.

- **Trade-off**: The owner of a tenant can never lose the owner role
  via `members:update-role` (it would orphan the tenant). The use
  case rejects with `tenants.cannot_demote_owner`. The owner can
  transfer ownership via a separate `TransferOwnership` use case —
  **out of scope** for sprint 03, deferred to post-MVP per
  [ADR-0022](../../../docs/adr/0022-rbac-model.md).

- **Trade-off**: Invitations carry the proposed role in the signed
  token, so the inviter cannot change it after sending. To "change
  the role", cancel and re-invite. Acceptable for MVP.

## Migration Plan

- This change ships migration 0003. The `upgrade()` is reversible.
- Local: `make migrate` applies 0003 (ALTER tenants, CREATE
  tenant_members/invitations/permissions/role_permissions, RLS
  policies, owner partial index, catalog seed). The catalog seed
  imports `shared_kernel.permissions.catalog` so the migration MUST
  run from a checkout that contains the module (i.e. you can't
  upgrade 0003 against an older codebase).
- Rollback: `make migrate-down` rolls 0003 back: DROPs the four new
  tables (tenant_members, invitations, permissions,
  role_permissions), removes the columns added to `tenants`, drops
  the partial owner index. The `tenants` row may still hold tenants
  created before the rollback — the `name` column is preserved;
  fiscal columns are dropped.
- **AWS deploy: deferred.** Account verification pending. When the
  account clears, the Terraform side requires no new modules: the
  existing Cognito user-pool from sprint 01 already declares
  `custom:active_tenant`, and the IAM `cognito-idp:AdminUpdateUserAttributes`
  was granted in sprint 02. The post-deploy verification steps stay
  unchecked in `tasks.md`.

## Open Questions

- None blocking implementation. Re-evaluation triggers (tracked in
  [`docs/18-roadmap.md`](../../../docs/18-roadmap.md) and the
  relevant ADRs):
  - When does `TransferOwnership` ship? (Owner ergonomics, post-MVP.)
  - When does the hybrid-ownership repository mixin land? (Sprint 04
    with `Invoice` — first owned aggregate.)
  - When does the welcome-email worker pick up `MemberJoined`?
    (Sprint 08.)
  - Should the cache TTL drop below 60 s if a tenant requests
    immediate revocation? (Post-MVP — at that point introduce
    event-driven invalidation, not a shorter TTL.)
