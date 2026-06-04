## 1. Domain / application

- [x] 1.1 Add `InvitationIdentityMismatchError` to the tenants context errors module with code `invitation.identity_mismatch`.
- [x] 1.2 In `accept_invitation` use case, after decoding the invitation JWT, fetch the authenticated user email and compare `jwt.sub.casefold() == principal_email.casefold()`. On mismatch, raise `InvitationIdentityMismatchError`.
- [x] 1.3 Confirm the comparison happens BEFORE any state mutation (no membership row written, no jti consumed) so a failed attempt is a no-op.

## 2. HTTP mapping

- [x] 2.1 In `apps/api/src/contexts/tenants/adapters/inbound/http/errors.py`, map `InvitationIdentityMismatchError` to 403 Forbidden, Spanish title `Esta invitación no es para ti`, code `invitation.identity_mismatch`. Detail field SHALL NOT include the JWT sub.
- [x] 2.2 Confirm Spanish title is wired through the existing `ProblemDetails` model.

## 3. Frontend copy and UX

- [x] 3.1 Register `invitation.identity_mismatch` in `apps/web/src/api/errors.ts` with the documented Spanish copy.
- [x] 3.2 In `apps/web/src/routes/invitations/accept.tsx`, surface the typed error via `FormErrorAlert`. Offer a button "Cerrar sesión y volver a esta invitación" that calls logout then redirects to `/login?invite=<token>` (preserving the token so the user can retry after signing in under the invited email). Token preserved via `PENDING_INVITE_KEY` sessionStorage stash (the existing post-login bootstrap pops it).

## 4. Tests

- [x] 4.1 Backend unit (FakeRepo + canned JWT decode): mismatch raises typed error; match returns success. (`test_accept_invitation_identity_mismatch_is_noop`, `test_accept_invitation_email_compare_is_case_insensitive`).
- [x] 4.2 Backend integration: router maps the typed error to 403 + Spanish title + typed code; detail does not include the JWT sub (`test_accept_endpoint_returns_403_on_identity_mismatch`). Postgres+real-auth scenario covered by the same exception handler exercised under the in-process app.
- [x] 4.3 Frontend Vitest: 403 with `invitation.identity_mismatch` renders the Spanish copy; clicking the offered button calls `useLogoutMutation` and routes to `/login` with the token stashed for resume.

## 5. Validation

- [x] 5.1 `openspec validate bind-invitation-accept-to-invitee-identity --strict` exits 0.
