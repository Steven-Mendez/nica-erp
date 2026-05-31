## Why

The invited-user happy path captured during a pilot run (terminal
log on `make api`) still asks the user to re-type the password they
just typed on `/signup`, and then bounces a first-membership invitee
through the empresa picker even though there is only one empresa to
pick:

```
POST /v1/auth/register                       201
POST /v1/auth/confirm-signup                 204    # no tokens
POST /v1/auth/login                          200    # forced re-entry of credentials
POST /v1/invitations/accept                  200    # membership created
GET  /v1/tenants/<id>/invitations            403    # JWT lacks active_tenant
POST /v1/tenants/<id>/switch                 200    # JWT finally has active_tenant
```

Two independent endpoints each leave the caller in an interim
session state that the backend already has every input it needs to
finish:

1. `POST /v1/auth/confirm-signup` returns `204` even though the SPA
   could have shipped the just-typed password in the same request and
   received tokens immediately.
2. `POST /v1/invitations/accept` creates a `Membership` without
   touching the caller's `custom:active_tenant` claim, so the next
   tenant-scoped read returns `403` until a separate
   `/v1/tenants/{id}/switch` runs.

The result is a five-step ramp with one forced credential re-entry
and one picker detour. The user explicitly flagged the re-login step
as "estúpido". This change collapses the ramp to three steps with
neither detour, gated by
[`docs/adr/0035-onboarding-endpoints-return-session.md`](../../../docs/adr/0035-onboarding-endpoints-return-session.md).

References:
[`docs/sprints/03-tenants-and-rls.md` — Sprint follow-up — Invited-user onboarding lands session-ready](../../../docs/sprints/03-tenants-and-rls.md#sprint-follow-up--invited-user-onboarding-lands-session-ready-sprint-315-2026-05-31),
[ADR-0035](../../../docs/adr/0035-onboarding-endpoints-return-session.md),
[ADR-0031](../../../docs/adr/0031-invitation-token-transport.md).

## What Changes

### `confirm-signup` may return a session

- `POST /v1/auth/confirm-signup` accepts an optional `password` in
  its request body in addition to the existing `email` and `code`.
- When `password` is present and the code confirms successfully, the
  `ConfirmSignup` use case calls
  `IdentityProvider.authenticate(email, password)` in the same
  transaction and returns `200 OK` with
  `{ access_token, refresh_token, id_token, expires_in, token_type }`
  (the shape already used by `POST /v1/auth/login`).
- When `password` is absent the endpoint keeps its current
  `204 No Content` shape (backwards compatible — a `/confirm` page
  that lost its router state on a hard refresh still works).

### `accept-invitation` may rotate session for first-membership invitees

- `POST /v1/invitations/accept` accepts an optional `refresh_token`
  in its request body in addition to the existing `token`.
- After persisting the `Membership`, if the caller's validated
  `CurrentUserContext` has no prior `custom:active_tenant` claim, the
  `AcceptInvitation` use case calls
  `IdentityProvider.update_active_tenant(user_id, tenant_id)` followed
  by `IdentityProvider.refresh(refresh_token)` and returns the new
  bundle inside an optional `tokens` field.
- When the caller already had an `active_tenant` (veteran user
  accepting a second-empresa invitation), the use case skips both
  calls and the response omits `tokens`. The caller stays inside the
  empresa they were working on.
- The decision to rotate is taken from the **validated**
  `CurrentUserContext.active_tenant`, not from any field in the
  request body, to keep the side effect derived from authenticated
  state only (see [ADR-0035](../../../docs/adr/0035-onboarding-endpoints-return-session.md)
  Consequences).

### SPA wires the new shapes through

- `apps/web/src/routes/signup.tsx` forwards the typed password to
  `/confirm` via TanStack Router state (in-memory). On a hard refresh
  of `/confirm` the password is lost; the route falls back to its
  current behaviour (navigate to `/login` after confirm success).
- `apps/web/src/routes/confirm.tsx` reads `password` from router
  state. When present it posts to `confirm-signup` with the password,
  calls `storeTokens()` on the returned bundle, and invalidates the
  `meQueryKey`. The post-confirm navigation is delegated to the route
  guard.
- `apps/web/src/features/tenants/api/endpoints.ts` posts
  `{ token, refresh_token }` to `/v1/invitations/accept`. The client
  reads the optional `tokens` field on the response and calls
  `storeTokens()` before invalidating `meQueryKey` and `myTenantsKey`.
  When `tokens` is absent (veteran user case), no token store mutation
  happens.

## Impact

- Affected specs:
  - `identity-http` (modified — optional `password` on
    `/v1/auth/confirm-signup`, conditional `200` response shape)
  - `tenants-http` (modified — optional `refresh_token` on
    `/v1/invitations/accept`, conditional `tokens` field on the
    response)
  - `auth-frontend` (new — captures the SPA-observable behaviour of
    the seamless invited-user ramp and its hard-refresh fallback)
- Affected code:
  - `apps/api/src/contexts/identity/adapters/inbound/http/{router,schemas}.py`
  - `apps/api/src/contexts/identity/application/use_cases/confirm_signup.py`
  - `apps/api/src/contexts/tenants/adapters/inbound/http/{router,schemas}.py`
  - `apps/api/src/contexts/tenants/application/use_cases/accept_invitation.py`
  - `apps/web/src/routes/{signup,confirm}.tsx`
  - `apps/web/src/routes/invitations/accept.tsx`
  - `apps/web/src/features/auth/api/{endpoints,hooks}.ts` and
    `apps/web/src/features/tenants/api/endpoints.ts`
- Affected tests:
  - `apps/api/tests/integration/contexts/identity/http/test_auth_router.py`
    (add `confirm-signup` with-password + bare-204 cases)
  - `apps/api/tests/integration/contexts/tenants/http/test_invitations_router.py`
    (add first-membership-rotates-tokens + veteran-no-rotation cases)
  - `apps/api/tests/unit/contexts/identity/application/test_confirm_signup.py`
    (add password-branch unit case)
  - `apps/api/tests/unit/contexts/tenants/application/test_accept_invitation.py`
    (add `update_active_tenant` + `refresh` call assertion for the
    first-membership branch)
  - `apps/web/tests/e2e/invitation-accept.spec.ts` (remove `.fixme()`,
    extend to the seamless happy path)
  - New `apps/web/tests/e2e/invitation-accept-veteran.spec.ts`
    (existing-account-invited-to-second-empresa case)
  - New `apps/web/tests/e2e/signup-confirm-refresh-fallback.spec.ts`
    (`/confirm` hard refresh falls back to `/login` without breakage)
- Affected docs:
  - [`docs/adr/0035-onboarding-endpoints-return-session.md`](../../../docs/adr/0035-onboarding-endpoints-return-session.md)
    (new — already merged with this change)
  - [`docs/adr/README.md`](../../../docs/adr/README.md) (Auth &
    security index row added)
  - [`docs/sprints/02-identity-and-rbac.md`](../../../docs/sprints/02-identity-and-rbac.md)
    (post-sprint extensions pointer added)
  - [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md)
    (sprint 3.15 follow-up section added)

## Out of scope

- No change to `POST /v1/tenants` (first-empresa creation). A user
  who creates their own first empresa still goes through
  `POST /v1/tenants/{id}/switch` and the existing empresa-picker UX.
- No change to `POST /v1/auth/password/reset`. Landing back at
  `/login` after a reset is the documented behaviour.
- No new bounded context. The change extends the request bodies and
  response shapes of two existing endpoints owned by the `identity`
  and `tenants` contexts.
- No DB migration; no new column on `users` or on `memberships`.
- No `sessionStorage` / `localStorage` persistence for the typed
  password. Router state is in-memory only; the fallback path is
  explicit.
- No "always rotate tokens on accept" toggle. Veteran users joining a
  second empresa keep their current `active_tenant`; switching is a
  separate explicit action.
