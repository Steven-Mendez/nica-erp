## ADDED Requirements

### Requirement: `TenantMiddleware` is registered between Auth and routes

`bootstrap/api.create_app()` SHALL register `TenantMiddleware`
**before** `AuthMiddleware` in the `add_middleware` call sequence
(so Starlette's reverse-order rule places Auth as the outer layer
and Tenant as the inner layer). CORS, when enabled, remains the
outermost layer.

The order SHALL be — earliest add first:

```python
app.add_middleware(TenantMiddleware, uow_factory=build_request_uow)
app.add_middleware(AuthMiddleware, identity_provider=build_identity_provider_for_middleware())
if settings.app_env != "aws":
    app.add_middleware(CORSMiddleware, ...)
```

Runtime evaluation order is Auth → Tenant → routes; that lets
Tenant rely on `CurrentUserContext` populated by Auth.

#### Scenario: Auth runs before Tenant

- **GIVEN** a request whose JWT fails Auth's verify_token call
- **WHEN** the request enters the middleware stack
- **THEN** the 401 response from Auth SHALL be returned WITHOUT
  any database call by Tenant

### Requirement: Bootstrap exposes `current_actor` and `require`

`bootstrap/dependencies.py` SHALL declare:

- `async def current_actor(...) -> Actor` — the FastAPI dependency
  that materialises the request's `Actor` from
  `CurrentUserContext`, `TenantContext`, the `tenant_members`
  table, and the TTL-cached `role_permissions`.
- `def require(*codes: str) -> Callable[..., Awaitable[Actor]]` —
  the dependency factory that wraps `current_actor` and 403s on
  any missing code.

Both SHALL be importable from `bootstrap.dependencies` so any
context's router can declare
`Depends(require("..."))` without reaching into `shared_kernel`.

#### Scenario: Importing the dependency works

- **WHEN** a test imports `from bootstrap.dependencies import
  current_actor, require`
- **THEN** both symbols SHALL be accessible

### Requirement: Container builders cover the new tenant adapters

`bootstrap/container.py` SHALL expose:

- `build_tenant_repository(uow) -> TenantRepository`
- `build_membership_repository(uow) -> MembershipRepository`
- `build_invitation_repository(uow) -> InvitationRepository`
- `build_invitation_token_generator() -> InvitationTokenGenerator`

Each factory SHALL return the SQLAlchemy/JWT-backed implementation
shipped under
`contexts/tenants/adapters/outbound/`. The token generator SHALL
read `settings.local_jwt_secret`,
`settings.invitation_token_ttl_seconds`.

#### Scenario: Builders return live adapters

- **WHEN** the builders are called against a real `uow`
- **THEN** each return value SHALL satisfy the corresponding
  outbound port Protocol via `isinstance(..., Protocol)`

### Requirement: `_RequestUnitOfWork` sets GUCs on outer entry

`bootstrap/container._RequestUnitOfWork.begin()` SHALL, on the outer
entry (when `self._session is None` at call time), execute two
`SET LOCAL` statements before yielding:

1. `SET LOCAL app.tenant_id = :t` with `:t` = the current
   `TenantContext` UUID stringified, defaulting to the zero UUID
   `'00000000-0000-0000-0000-000000000000'` when unset.
2. `SET LOCAL app.current_user_id = :u` with `:u` = the
   `CurrentUserContext.user_id` stringified, defaulting to the same
   zero UUID when no current user is present.

The inner reentrant branch SHALL remain a no-op (the outer
transaction's `SET LOCAL` already applies).

#### Scenario: Outer entry sets both GUCs

- **GIVEN** `TenantContext.set(<T>)` and `CurrentUserContext.set(<U>)`
- **WHEN** `_RequestUnitOfWork.begin()` is entered for the first
  time
- **THEN** within the yielded session, `SELECT current_setting('app.tenant_id', true)`
  SHALL return `str(<T>)` and `SELECT current_setting('app.current_user_id', true)`
  SHALL return `str(<U>.user_id)`

### Requirement: `import-linter` covers the new tenants module

`apps/api/.importlinter` (or whatever file holds the
`domain-purity` contract) SHALL extend the contract to forbid
`contexts.tenants.domain` from importing `sqlalchemy`, `fastapi`,
`boto3`, any `contexts.tenants.{application,adapters}` module, or
any other `contexts.<x>` package. A second contract SHALL forbid
`shared_kernel.permissions.catalog` from importing `sqlalchemy`,
`fastapi`, or any `contexts.*` package. A third contract SHALL
forbid productive modules (`contexts/*/adapters/`,
`contexts/*/application/`, `bootstrap/`) from importing
`contexts.identity.testing`.

#### Scenario: Productive code importing `forge_jwt` fails the linter

- **GIVEN** a candidate adapter that adds `from
  contexts.identity.testing import forge_jwt`
- **WHEN** `uv run lint-imports` runs
- **THEN** the contract violation SHALL be reported and the
  command SHALL exit non-zero
