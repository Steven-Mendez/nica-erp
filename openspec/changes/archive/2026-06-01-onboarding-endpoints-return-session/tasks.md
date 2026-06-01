## 1. Backend — `confirm-signup` returns optional session

- [x] 1.1 Extend `ConfirmSignupRequest` Pydantic schema in
      `apps/api/src/contexts/identity/adapters/inbound/http/schemas.py`
      with an optional `password: SecretStr | None = None` field
      next to `email` and `code`. Add a `TokenBundleResponse`
      mirroring the existing `TokenResponse` (or reuse it directly).
- [x] 1.2 Update the `ConfirmSignup` use case at
      `apps/api/src/contexts/identity/application/use_cases/confirm_signup.py`
      so its `execute` signature accepts an optional `password`. When
      present, after the existing confirm + user-aggregate persistence,
      call `identity_provider.authenticate(email, password)` and
      return the resulting `Identity` bundle. When absent, return the
      current `None`.
- [x] 1.3 Update the FastAPI route at
      `apps/api/src/contexts/identity/adapters/inbound/http/router.py`
      so the response model is `TokenResponse | None`. When the use
      case returns tokens, respond `200` with the bundle; otherwise
      respond `204` (current behaviour). Use FastAPI's `response_model`
      / dynamic response shape conventions already in the file.
- [x] 1.4 Unit test
      `apps/api/tests/unit/contexts/identity/application/test_confirm_signup.py`:
      add `test_execute_with_password_returns_identity_bundle` and
      `test_execute_without_password_returns_none` cases. Keep the
      existing assertions on the `UserRegistered` outbox event.
- [x] 1.5 Integration test
      `apps/api/tests/integration/contexts/identity/http/test_auth_router.py`:
      add `test_confirm_signup_with_password_returns_tokens` (asserts
      the response has `access_token`, `refresh_token`, `id_token` and
      that an immediate `GET /v1/me` with the access token returns
      `200` and the freshly-created user) and
      `test_confirm_signup_without_password_returns_204` (asserts the
      `204` shape is preserved and a follow-up `POST /v1/auth/login`
      still works as before).

## 2. Backend — `accept-invitation` rotates session for first membership

- [x] 2.1 Extend `AcceptInvitationRequest` Pydantic schema in
      `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`
      with an optional `refresh_token: str | None = None`. Add an
      optional `tokens: TokenBundle | None` field on
      `AcceptInvitationResponse` (reuse the identity-context bundle
      via cross-context schema import or duplicate the shape if the
      hexagonal boundary forbids it — see project layout).
- [x] 2.2 Update `AcceptInvitation` use case at
      `apps/api/src/contexts/tenants/application/use_cases/accept_invitation.py`
      to take the caller's prior `active_tenant` and the optional
      `refresh_token` as inputs. After persisting the `Membership`
      and emitting the `MemberJoined` event, if and only if the
      caller had no prior `active_tenant` and a `refresh_token` is
      supplied, call
      `identity_provider.update_active_tenant(user_id, tenant_id)`
      then `identity_provider.refresh(refresh_token)` and return the
      bundle. Otherwise return `None`.
- [x] 2.3 Update the FastAPI route at
      `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`
      so it reads the prior `active_tenant` from
      `CurrentUserContext`, **not** from any decoded form of the
      request body, and threads it into the use case. The response
      keeps its `{ tenant_id, role }` shape and adds `tokens` only
      when the use case returns one.
- [x] 2.4 Unit test
      `apps/api/tests/unit/contexts/tenants/application/test_accept_invitation.py`:
      add `test_first_membership_with_refresh_token_rotates_session`
      (asserts `update_active_tenant` and `refresh` are called and
      the returned bundle is the one the IdP mock produced) and
      `test_veteran_caller_skips_rotation` (asserts neither
      `update_active_tenant` nor `refresh` is called and the response
      has `tokens=None`).
- [x] 2.5 Integration test
      `apps/api/tests/integration/contexts/tenants/http/test_invitations_router.py`:
      add `test_accept_first_membership_returns_rotated_tokens`
      (decode the returned `access_token` and assert
      `custom:active_tenant == invited_tenant_id`; then `GET /v1/me`
      with that token shows the invited tenant; then
      `GET /v1/tenants/<id>/invitations` returns `200`, not `403`)
      and `test_accept_second_membership_preserves_active_tenant`
      (asserts the response omits `tokens` and a follow-up
      `GET /v1/me` still shows the prior empresa).

## 3. Frontend — pass password from signup to confirm

- [x] 3.1 In `apps/web/src/routes/signup.tsx`, after a successful
      `POST /v1/auth/register`, navigate to `/confirm` with the
      typed password in TanStack Router state (not in the URL).
- [x] 3.2 In `apps/web/src/routes/confirm.tsx`, read the password
      from router state. When present, post it alongside `email` and
      `code` to `confirm-signup`; on a token bundle response, call
      `storeTokens()` from `apps/web/src/api/tokenStore.ts` and
      invalidate `meQueryKey`. When absent (hard refresh of
      `/confirm`), keep the current "navigate to `/login`" fallback
      and DO NOT call `confirm-signup` with a password.
- [x] 3.3 Update `ConfirmSignupInput` and the mutation hook in
      `apps/web/src/features/auth/api/{endpoints,hooks}.ts` so the
      request type carries an optional `password` and the response
      type is `TokenResponse | void`. Hook callers in §3.2 read the
      narrowed branch.
- [x] 3.4 Frontend unit / integration tests for `confirm.tsx` cover
      both branches: with-password autostores tokens and invalidates
      `meQueryKey`; without-password navigates to `/login`.

## 4. Frontend — auto-store tokens after accept-invitation

- [x] 4.1 In `apps/web/src/features/tenants/api/endpoints.ts`,
      change `acceptInvitation(token)` to
      `acceptInvitation({ token, refresh_token })`. The hook reads
      the current refresh token from `tokenStore` and forwards it.
- [x] 4.2 In `apps/web/src/routes/invitations/accept.tsx`, after a
      successful accept response, if the response includes `tokens`,
      call `storeTokens(tokens)` before invalidating `meQueryKey`
      and `myTenantsKey`. Keep the existing `setPickerConfirmed()`
      call so the route guard does not bounce the user back to the
      empresa picker. Veteran-user case (no `tokens` in response)
      keeps the current behaviour.
- [x] 4.3 Frontend unit / integration tests for
      `invitations/accept.tsx` cover both branches: first-membership
      (response includes `tokens`) calls `storeTokens` and lands on
      `/dashboard`; veteran (response omits `tokens`) does not call
      `storeTokens` and still lands on `/dashboard` per
      `setPickerConfirmed`.

## 5. End-to-end coverage

- [x] 5.1 Remove the `.fixme()` from
      `apps/web/tests/e2e/invitation-accept.spec.ts` and extend the
      spec to assert the seamless happy path: owner invites →
      invitee opens email link → preview → signup → confirm with
      code → lands on `/dashboard` of the invited empresa. No
      `/login` step. No `/tenants` (picker) step. Assert by URL and
      by an empresa-specific h1.
- [x] 5.2 New spec
      `apps/web/tests/e2e/invitation-accept-veteran.spec.ts`:
      veteran user already authenticated in their own empresa A
      accepts an invitation to empresa B. After accept, the URL is
      still empresa-A-scoped (no auto-switch) and the sidebar still
      shows empresa A as active. The invited empresa is reachable
      via `OrganizationSwitcher`.
- [x] 5.3 New spec
      `apps/web/tests/e2e/signup-confirm-refresh-fallback.spec.ts`:
      drive the SPA through `/signup` → `/confirm`, hard-reload
      `/confirm`, then submit the email code. The flow falls back
      to the documented `/login` redirect, the user logs in
      manually, and a follow-up `GET /v1/me` shows the confirmed
      user. No JS console errors.
- [x] 5.4 Run `pnpm e2e -- --grep="invitation|signup"` locally
      against the make-api stack to confirm all three specs pass.

## 6. Wrap-up

- [x] 6.1 `make api-test` and `pnpm test --run` and
      `pnpm typecheck` exit 0.
- [x] 6.2 `pnpm gen:api` regenerates `apps/web/src/api/schema.d.ts`
      with the new optional fields; commit the regen separately.
- [x] 6.3 Verify the seamless flow manually in `make api` + `pnpm dev`
      against Mailpit: register, copy code, confirm — the SPA lands
      authenticated on the invited dashboard without any extra step.
- [x] 6.4 Update the OpenSpec change status to "ready for archive"
      once §1–§5 are green; archive by moving the directory under
      `openspec/changes/archive/<YYYY-MM-DD>-onboarding-endpoints-return-session/`.
