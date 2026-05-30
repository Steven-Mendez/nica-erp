## ADDED Requirements

### Requirement: `shared_kernel.permissions.catalog` is the source of truth

`apps/api/src/shared_kernel/permissions/catalog.py` SHALL declare:

- A frozen `Permission` dataclass with fields `code: str`,
  `resource: str`, `action: str`, `scope: Literal["own","all","na"]`,
  `description: str`.
- `TENANT_PERMISSIONS: tuple[Permission, ...]` listing exactly the
  six sprint-03 permissions: `tenant:read`, `tenant:write`,
  `members:read`, `members:invite`, `members:update-role`,
  `members:remove`, all with `scope="na"`.
- `ROLES: tuple[str, ...] = ("viewer", "salesperson", "accountant",
  "admin", "owner")` — order matches the privilege ascent.
- `DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]]` populated
  from the sprint 03 matrix in
  [`docs/06-security-model.md` §Role-to-permission default matrix](../../../../docs/06-security-model.md#role-to-permission-default-matrix).

The module SHALL NOT import `sqlalchemy`, `fastapi`, `boto3`, or
any `contexts.*` package — enforced by import-linter.

#### Scenario: Catalog shape is stable

- **WHEN** the module is imported and `len(TENANT_PERMISSIONS)` is
  evaluated
- **THEN** the result SHALL be exactly 6

#### Scenario: Owner has every tenant-context permission

- **WHEN** `DEFAULT_ROLE_PERMISSIONS["owner"]` is compared to the set
  of every `code` in `TENANT_PERMISSIONS`
- **THEN** the two sets SHALL be equal

### Requirement: `Actor` is the request-scoped authorization context

`shared_kernel.permissions.actor.Actor` SHALL be a frozen dataclass
with `user_id: UUID`, `tenant_id: UUID | None`,
`role: str | None`, `permissions: frozenset[str]`. The constructor
SHALL accept defaults `tenant_id=None`, `role=None`,
`permissions=frozenset()` so the "no tenant active" branch of
`current_actor` can construct one.

#### Scenario: Default actor has no permissions

- **WHEN** `Actor(user_id=u)` is constructed without other fields
- **THEN** `permissions` SHALL be the empty `frozenset()` and
  `role` SHALL be `None`

### Requirement: Permission cache is process-local with TTL 60 s

`shared_kernel.permissions.cache.PermissionCache` (or equivalent
free-function pair `get_permissions / clear_permissions`) SHALL
expose `async get(role: str, session) -> frozenset[str]` backed by
a module-level dict guarded by an `asyncio.Lock` on the cache-miss
path. Entries SHALL expire after 60 s. The TTL SHALL be derived
from `settings.permission_cache_ttl_seconds` so tests can lower it.

A concurrent burst of cache misses for the same role SHALL execute
exactly **one** database query — the lock SHALL prevent the
thundering-herd.

#### Scenario: Repeated calls within 60 s hit the cache

- **WHEN** two `await cache.get("admin", session)` calls happen
  within 60 s of each other
- **THEN** the underlying `session.execute(...)` SHALL be called
  exactly once

#### Scenario: TTL expiry refetches

- **WHEN** the second call happens after a forced TTL of 0
- **THEN** `session.execute(...)` SHALL be called twice

### Requirement: `current_actor` materialises `Actor` per request

`bootstrap/dependencies.current_actor(request, session)` SHALL be a
FastAPI dependency. It SHALL:

1. Pull `CurrentUserContext.get()`; if `None`, raise 401
   `auth.invalid_credentials`.
2. Pull `TenantContext.get()`; if `None`, return
   `Actor(user_id=user.user_id, tenant_id=None, role=None,
   permissions=frozenset())`.
3. Query `tenant_members(user_id, tenant_id)` for the role; if
   absent (race with a membership removal) raise 403
   `tenant.not_member`.
4. Resolve permissions via the TTL cache.
5. Return `Actor(user_id, tenant_id, role, permissions)`.

#### Scenario: Tenant active → permissions resolved

- **WHEN** the dependency runs with `TenantContext` populated and a
  matching `tenant_members` row whose role is `admin`
- **THEN** the returned `Actor.role` SHALL be `"admin"` and
  `Actor.permissions` SHALL equal
  `DEFAULT_ROLE_PERMISSIONS["admin"]` (after sprint 03's seed)

### Requirement: `require(*codes)` 403s on a missing code

`bootstrap/dependencies.require(*codes: str)` SHALL return a
FastAPI dependency that consumes `Actor = Depends(current_actor)`
and raises `ForbiddenError(missing=[...])` listing each code the
actor lacks. An empty `missing` list SHALL pass through (the actor
is permitted).

#### Scenario: Multiple missing codes are all listed

- **WHEN** an actor without `members:invite` AND without
  `members:remove` calls a route declaring
  `Depends(require("members:invite", "members:remove"))`
- **THEN** the 403 problem body SHALL include
  `"missing": ["members:invite", "members:remove"]` (or a
  permutation thereof)

### Requirement: `ForbiddenError` maps to RFC-7807 with type `missing-permission`

`ForbiddenError` SHALL be a domain exception with field
`missing: list[str]`. The FastAPI exception handler SHALL serialise
it to HTTP 403 `application/problem+json` with `type` ending in
`/errors/missing-permission`, `title="Missing permission"`,
`code="missing-permission"`, and the `missing` array as a
top-level extension field
([ADR-0015](../../../../docs/adr/0015-rfc7807-errors.md)).

#### Scenario: Problem body carries `missing` extension

- **WHEN** the exception handler renders `ForbiddenError(missing=["tenant:write"])`
- **THEN** the JSON body SHALL include `"missing": ["tenant:write"]`
  as a top-level field

### Requirement: Sprint-gate test 1 — permission matrix DB vs Python agreement

Test `tests/integration/shared_kernel/permissions/test_role_permission_matrix.py::test_role_permission_matrix`
SHALL enumerate `role_permissions` from a freshly-migrated database
and compare to `DEFAULT_ROLE_PERMISSIONS` from the catalog module.
Any difference SHALL fail the test. This is a sprint-gate test:
the test marker SHALL be `integration` and the test SHALL be
selected by `make lint && make test`.

#### Scenario: Matrix matches catalog → pass

- **WHEN** the freshly-seeded `role_permissions` table is read and
  compared to `DEFAULT_ROLE_PERMISSIONS`
- **THEN** the test SHALL pass

### Requirement: Sprint-gate test 2 — endpoint coverage

Test `tests/integration/bootstrap/test_endpoint_permission_coverage.py::test_all_endpoints_require_permission`
SHALL iterate every route registered on the FastAPI app and
require that each non-public route either:

- declares at least one `Depends(require(...))` in its dependency
  graph, OR
- is in the explicit `NO_TENANT_REQUIRED` allowlist, OR
- is in the unauthenticated allowlist.

Any route outside those three categories SHALL fail the test.

#### Scenario: A route without a permission gate fails

- **GIVEN** a test fixture adds a route at `/v1/secret` with no
  `Depends(require(...))` and no allowlist entry
- **WHEN** the test runs
- **THEN** the test SHALL fail with a message naming `/v1/secret`
