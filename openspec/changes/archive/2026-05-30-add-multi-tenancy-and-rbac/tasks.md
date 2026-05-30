## 1. Dependencies and settings

- [x] 1.1 Confirm no new runtime deps; reuse `pyjwt[crypto]` from
      sprint 02 for invitation token signing.
- [x] 1.2 Extend `bootstrap/settings.py` with
      `invitation_token_ttl_seconds=604800` (7 days) and
      `permission_cache_ttl_seconds=60`.

## 2. RBAC catalog (`shared_kernel/permissions/`)

- [x] 2.1 Create `shared_kernel/permissions/__init__.py` re-exporting
      `Permission`, `TENANT_PERMISSIONS`, `ROLES`,
      `DEFAULT_ROLE_PERMISSIONS`, `Actor`.
- [x] 2.2 `catalog.py`: `Permission` frozen dataclass; the six
      `tenant:*` / `members:*` permissions tuple; `ROLES` tuple in
      ascending privilege order; `DEFAULT_ROLE_PERMISSIONS` mapping.
- [x] 2.3 `actor.py`: `Actor` frozen dataclass with `user_id`,
      `tenant_id`, `role: str | None`, `permissions: frozenset[str]`.
- [x] 2.4 `cache.py`: TTL-60s process-local cache over
      `(role → frozenset[str])` with `asyncio.Lock`-guarded fetch
      path.
- [x] 2.5 Author import-linter contract: `shared_kernel.permissions.catalog`
      MUST NOT import `sqlalchemy`, `fastapi`, `boto3`, or any
      `contexts.*` module.
- [x] 2.6 Unit tests: catalog shape, role ordering, cache miss/hit,
      cache TTL expiry.

## 3. Domain (`contexts/tenants/domain/`)

- [x] 3.1 `Ruc` VO: 14-character Nicaragua RUC, structural validation
      (digits + suffix); raises `ValueError` on invalid input.
- [x] 3.2 `Municipality` VO: enum-like wrapper over a frozen tuple of
      known municipalities (extensible: catalog list lives in
      `domain/municipality.py`).
- [x] 3.3 `Regime` VO: literal `general` / `simplified`.
- [x] 3.4 `AuthorizationDgi` VO: `number: str`, `valid_from: date`,
      `valid_to: date`; validates `valid_from <= valid_to`.
- [x] 3.5 `Role` enum: `owner`, `admin`, `accountant`, `salesperson`,
      `viewer`. `Role.from_str()` raises on unknown strings.
- [x] 3.6 `Tenant` aggregate (`AggregateRoot[UUID]`): fields
      `name`, `ruc`, `regime`, `municipality`, `authorization_dgi`,
      `fiscal_address`, `is_withholder`, `status`, `created_at`,
      `updated_at`. Class method `register(...)` records
      `TenantCreated v1`. `update_fiscal(...)` mutates the mutable
      subset.
- [x] 3.7 `Membership` entity: `user_id`, `tenant_id`, `role`,
      `status`, `joined_at`, `removed_at`. Class method
      `create_owner(...)` is the only constructor that sets
      `role='owner'` (so the use case is the gatekeeper).
- [x] 3.8 `Invitation` entity: `tenant_id`, `email`, `proposed_role`,
      `token_hash`, `expires_at`, `status` (`pending`/`accepted`/
      `cancelled`/`expired`), `cancelled_at`, `created_at`.
- [x] 3.9 Events `TenantCreated v1`, `MemberInvited v1`,
      `MemberJoined v1`, `MemberRemoved v1`, `InvitationCancelled v1`,
      `MemberRoleChanged v1` — frozen kw-only `DomainEvent`
      subclasses with stable payloads.
- [x] 3.10 Unit tests for every VO (valid + invalid), the two
      aggregate factories, and the six events.

## 4. Application (`contexts/tenants/application/`)

- [x] 4.1 Outbound ports (Protocols):
      - `TenantRepository`: `get`, `add`, `update`, `list_for_user`.
      - `MembershipRepository`: `get`, `add`, `update`, `remove`,
        `list_by_tenant`, `find`.
      - `InvitationRepository`: `add`, `get_by_token_hash`, `update`,
        `list_by_tenant`.
      - `InvitationTokenGenerator`: `mint(tenant_id, email, role)
        -> (token, token_hash, expires_at)`, `verify(token) -> claims`.
- [x] 4.2 Use cases (keyword-only dataclasses with `execute()`):
      `CreateTenant`, `GetMyTenants`, `GetTenant`, `UpdateTenant`,
      `InviteMember`, `AcceptInvitation`, `CancelInvitation`,
      `RemoveMember`, `SwitchActiveTenant`.
- [x] 4.3 `CreateTenant` inserts `Tenant` + owner `Membership` in
      one UoW, emits `TenantCreated v1` to outbox with
      `tenant_id=<the new id>`. The caller is the owner.
- [x] 4.4 `InviteMember` validates role ≠ `owner` (owner is created
      only via `CreateTenant`), mints a signed token, persists the
      hash, emits `MemberInvited v1`, calls `EmailSender.send(...)`
      with the invitation URL (use case-level synchronous send, like
      sprint 02 signup verification).
- [x] 4.5 `AcceptInvitation` (public): verifies the token, finds
      the invitation by hash, atomically inserts the
      `tenant_members` row + flips invitation to `accepted` +
      emits `MemberJoined v1`. Uses the system-global tenant
      sentinel? No — the outbox row gets `tenant_id=<invitation.tenant_id>`.
- [x] 4.6 `SwitchActiveTenant` calls
      `IdentityProvider.update_active_tenant(external_sub, tenant_id)`,
      then mints a fresh `Identity` by calling `IdentityProvider.refresh(refresh_token=...)`
      (the SPA sends its refresh token in the body). Returns the
      new `Identity`.
- [x] 4.7 `RemoveMember` rejects with `tenants.cannot_remove_owner`
      if the target role is `owner`.
- [x] 4.8 Domain errors: `TenantNotFoundError`, `NotAMemberError`,
      `InvitationExpiredError`, `InvitationAlreadyAcceptedError`,
      `CannotRemoveOwnerError`, `CannotDemoteOwnerError`,
      `OwnerAlreadyExistsError`.
- [x] 4.9 Unit tests per use case with mocked ports.

## 5. Infrastructure adapters (`contexts/tenants/adapters/outbound/`)

- [x] 5.1 SQLAlchemy mappers: `TenantRow`, `TenantMemberRow`,
      `InvitationRow`.
- [x] 5.2 `TenantRepositorySqlAlchemy`, `MembershipRepositorySqlAlchemy`,
      `InvitationRepositorySqlAlchemy` — each binds to
      `uow.current_session`; aggregate ↔ row mappers stay in
      `adapters/`, never in `domain/`.
- [x] 5.3 `InvitationTokenGeneratorJwt`: HS256 with
      `settings.local_jwt_secret`; SHA-256 hash of the encoded
      token; TTL from `settings.invitation_token_ttl_seconds`.
- [x] 5.4 Integration tests against the Postgres testcontainer:
      round-trip add/get; RLS check (without `SET LOCAL` the
      query returns zero rows; with `SET LOCAL` it returns the
      tenant's rows only).

## 6. Multi-tenancy middleware + UoW GUC injection

- [x] 6.1 Extend `_RequestUnitOfWork.begin()` in
      `bootstrap/container.py` to `SET LOCAL app.tenant_id` and
      `SET LOCAL app.current_user_id` on the outer entry. The
      reentrant inner branch is unchanged.
- [x] 6.2 New `TenantMiddleware` in
      `contexts/tenants/adapters/inbound/http/middleware.py`. It
      reads `CurrentUserContext.active_tenant`, validates membership
      (one-shot UoW), sets `TenantContext`. 403 `tenant.not_member`
      on missing membership.
- [x] 6.3 Register `TenantMiddleware` in `bootstrap/api.py` between
      `AuthMiddleware` and routes (see §Decisions in design.md for
      the add-order).
- [x] 6.4 Integration test: a request to a tenant-scoped endpoint
      with a JWT whose `custom:active_tenant` is a real but
      unauthorized tenant returns 403 `tenant.not_member`.

## 7. `current_actor` + `require` dependency

- [x] 7.1 `bootstrap/dependencies.py.current_actor`: pulls
      `CurrentUserContext` + `TenantContext`, queries
      `tenant_members` for role, queries `role_permissions` via
      the TTL cache, returns `Actor`.
- [x] 7.2 `bootstrap/dependencies.py.require(*codes)`: FastAPI
      dependency that 403s with `ForbiddenError(missing=...)` on
      a missing code.
- [x] 7.3 `ForbiddenError` and its handler in
      `bootstrap/api.py` (or in `shared_kernel/adapters/errors.py`
      if a shared location is introduced — sprint 02 uses
      `contexts/identity/adapters/inbound/http/errors.py` as the
      handler-registration site; this change adds the new error
      types there).
- [x] 7.4 Integration test: a route with `Depends(require("members:read"))`
      returns 403 for a `viewer`, 200 for an `admin`.

## 8. HTTP adapters (`contexts/tenants/adapters/inbound/http/`)

- [x] 8.1 Router under `/v1/tenants/`: `POST /`, `GET /me`,
      `GET /{id}`, `PATCH /{id}` (`tenant:write`),
      `POST /{id}/switch`, `GET /{id}/members` (`members:read`),
      `PATCH /{id}/members/{user_id}` (`members:update-role`),
      `DELETE /{id}/members/{user_id}` (`members:remove`),
      `GET /{id}/invitations` (`members:read`),
      `POST /{id}/invitations` (`members:invite`),
      `DELETE /{id}/invitations/{invitation_id}` (`members:invite`).
- [x] 8.2 Router under `/v1/invitations/`:
      `POST /{token}/accept` (public; already allowlisted).
- [x] 8.3 Pydantic request/response schemas per endpoint;
      RFC-7807 problem details with stable codes:
      `tenants.ruc_taken`, `tenants.cannot_remove_owner`,
      `tenants.cannot_demote_owner`, `invitation.expired`,
      `invitation.already_accepted`, `tenant.not_member`,
      `missing-permission`.
- [x] 8.4 Extend `GET /v1/me` response with `role` and
      `permissions`. The identity router's `get_me` use case stays
      identity-only; the HTTP layer composes the actor from
      `current_actor` and overlays it onto the response. (Avoids
      cross-context import in the application layer.)
- [x] 8.5 Add `POST /v1/tenants` to the `NO_TENANT_REQUIRED`
      allowlist confirmation (already present from sprint 02 — verify
      with a regression test).
- [x] 8.6 Router-level integration tests using `httpx.AsyncClient`
      over the ASGI app, against the Postgres testcontainer.

## 9. Bootstrap wiring

- [x] 9.1 `bootstrap/container.py` gains
      `build_tenant_repository(uow)`, `build_membership_repository(uow)`,
      `build_invitation_repository(uow)`, `build_invitation_token_generator()`.
- [x] 9.2 Extend `bootstrap/api.py` to mount the new tenant router
      and register `TenantMiddleware`.
- [x] 9.3 Extend the `domain-purity` contract in
      `apps/api/.importlinter` to cover `contexts.tenants.domain`
      (no `sqlalchemy`, `fastapi`, `boto3`, cross-context, or
      own-context adapters/application imports).

## 10. Alembic migration 0003

- [x] 10.1 Author `0003_tenants_and_rbac.py` with
      `down_revision='0002_identity'`.
- [x] 10.2 ALTER `tenants`: add fiscal columns, `status` column with
      CHECK, `updated_at`. `tenants.name` UNIQUE constraint
      remains; add `ruc` UNIQUE.
- [x] 10.3 CREATE `tenant_members` with the special RLS policy
      (`USING` on `user_id OR tenant_id`; `WITH CHECK` on
      `tenant_id`). Add the partial unique index on
      `(tenant_id) WHERE role='owner' AND status='active'`.
- [x] 10.4 CREATE `invitations` with the canonical RLS policy
      (`USING` + `WITH CHECK` same expression on
      `app.tenant_id`).
- [x] 10.5 CREATE `permissions` and `role_permissions` (global, no
      RLS). Seed from
      `shared_kernel.permissions.catalog.TENANT_PERMISSIONS`
      and `DEFAULT_ROLE_PERMISSIONS` via `op.bulk_insert(...)`
      with `ON CONFLICT DO NOTHING`.
- [x] 10.6 Reversible `downgrade()` that drops `role_permissions`,
      `permissions`, `invitations`, `tenant_members`, the partial
      owner index, then the columns added to `tenants`.
- [x] 10.7 Log a summary of seeded counts so operators see
      `[migration 0003] permissions: 6 inserted, role_permissions: 22 inserted`.

## 11. Identity adapter deltas + testing helper

- [x] 11.1 Add `contexts/identity/testing.py` with `forge_jwt(*,
      user_id, email, active_tenant, secret, **claims) -> str` that
      reuses the HS256 encoder of `IdentityProviderLocal` to mint a
      byte-identical token.
- [x] 11.2 Extend the `domain-purity` import-linter contract to
      forbid `contexts.identity.testing` from being imported by
      any module under `contexts/*/adapters/`,
      `contexts/*/application/`, or `bootstrap/`.
- [x] 11.3 Unit test: `IdentityProviderLocal.update_active_tenant`
      causes the next `authenticate(...)` to emit a JWT whose
      `custom:active_tenant` is the new value.
- [x] 11.4 Unit test (mocked client):
      `IdentityProviderCognito.update_active_tenant` calls
      `AdminUpdateUserAttributes` exactly once with
      `Name="custom:active_tenant"`.

## 12. Frontend — `features/tenants/` + Topbar

- [x] 12.1 Regenerate `apps/web/src/api/schema.d.ts` from the
      running API (`pnpm gen:api`) and commit.
- [x] 12.2 Zod schemas under `apps/web/src/features/tenants/schemas/`:
      `createTenantSchema`, `updateTenantSchema`,
      `inviteMemberSchema`, `updateMemberRoleSchema`.
- [x] 12.3 Hooks under `apps/web/src/features/tenants/api/`:
      `useMyTenants`, `useTenant`, `useCreateTenant`,
      `useUpdateTenant`, `useMembers`, `useInviteMember`,
      `useRemoveMember`, `useUpdateMemberRole`, `useInvitations`,
      `useCancelInvitation`, `useAcceptInvitation`,
      `useSwitchTenant`.
- [x] 12.4 Routes under `apps/web/src/routes/`: `/tenants/new`,
      `/tenants/index`, `/tenants/$tenantId/members`,
      `/invitations/$token/accept`.
- [x] 12.5 `Topbar` component under
      `apps/web/src/components/topbar/`, rendered by `__root.tsx`
      when `CurrentUser.activeTenant` is set. `TenantSwitcher`
      lives inside the Topbar.
- [x] 12.6 `useHasPermission(code: string)` helper in
      `apps/web/src/api/` reading from the `useCurrentUser()`
      query.
- [x] 12.7 Vitest unit tests for `TenantSwitcher` (mocked fetch:
      switch triggers `queryClient.clear()` + `router.invalidate()`)
      and `useHasPermission`.

## 13. Tests

- [x] 13.1 Unit: every VO, every aggregate factory, every use case
      with mocked ports.
- [x] 13.2 Integration: repositories round-trip with RLS active;
      `TenantMiddleware` happy + 403 paths.
- [x] 13.3 **Sprint gate test 1** — `test_tenant_isolation_via_rls`:
      two tenants, the cross-tenant peek returns 404; a forged
      JWT for user B claiming tenant A returns 403.
- [x] 13.4 **Sprint gate test 2** — `test_role_permission_matrix`:
      enumerate `role_permissions` and compare to
      `DEFAULT_ROLE_PERMISSIONS`. Difference → fail.
- [x] 13.5 **Sprint gate test 3** — `test_all_endpoints_require_permission`:
      iterate the FastAPI route table; every non-public route must
      either be in `NO_TENANT_REQUIRED` allowlist OR declare at
      least one `Depends(require(...))`.
- [x] 13.6 **Sprint gate test 4** — `test_403_vs_404`: a `viewer`
      attempting `PATCH /v1/tenants/{id}` (tenant:write) returns
      403; a viewer requesting `/v1/tenants/{another_id}` returns
      404.
- [x] 13.7 Contract test `IdentityProvider.update_active_tenant`
      parametrised over Local and Cognito (Cognito skipped without
      AWS creds).

## 14. Verification

- [x] 14.1 Local: `make local-up && make migrate && make api`; run
      the `curl` flow from the sprint doc's
      [§Verifiable outcome (local)](../../../docs/sprints/03-tenants-and-rls.md#verifiable-outcome-local).
- [x] 14.2 Local: SPA flow — sign up two users in two private
      windows, each creates a tenant, A invites B, B accepts via
      `/invitations/$token/accept`, B switches to A's tenant via
      the `TenantSwitcher`.
- [x] 14.3 Lint: `make lint` + `uv run lint-imports`
      (domain-purity includes `contexts.tenants.domain` and
      `shared_kernel.permissions.catalog`).
- [x] 14.4 Frontend: `pnpm typecheck && pnpm test && pnpm lint`.
- [ ] 14.5 **AWS deploy: deferred** — account in verification.
      Item kept unchecked so the closure note has a single line
      to flip when the account clears. No code change needed at
      that point (the Cognito user-pool + IAM are already in place
      from sprint 02).
