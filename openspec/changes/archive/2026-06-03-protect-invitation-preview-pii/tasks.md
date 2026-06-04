## 1. Backend — preview response

- [x] 1.1 `InvitationPreviewResponse` in `apps/api/src/contexts/tenants/adapters/inbound/http/router.py` exposes only `organization_name` and `role`. (The schema lives inline on the public router; no separate `InvitationPreviewOut` exists.)
- [x] 1.2 The router's `preview_invitation` handler returns only those two fields. There is no separate use case for the preview path — the router talks to the invitation repo directly with the token hash.
- [x] 1.3 OpenAPI updated via the response_model change. `apps/web/src/api/schema.d.ts` synced.

## 2. Backend — accept body

- [x] 2.1 `AcceptInvitationByBodyRequest.confirmed_email: str | None = None` added in the public router schema.
- [x] 2.2 `accept_invitation` use case checks `confirmed_email.casefold() == claims.email.casefold()` BEFORE the existing identity-binding check; mismatch raises `InvitationIdentityMismatchError` (same 403 + Spanish copy from change #1).
- [x] 2.3 The body docstring on `AcceptInvitationByBodyRequest` documents the audit F-026 defense-in-depth motivation.

## 3. Frontend — accept screen

- [x] 3.1 The accept route already parses the hash token, strips it via `history.replaceState`, and (for unauthenticated visitors) calls `previewInvitation` to validate the token.
- [ ] 3.2 Required "Confirma tu correo" retype input — deferred. The current accept route binds the invitation to the authenticated user's email; adding the retype field is a UI enhancement that benefits from browser smoke. The backend accepts the field today (defense in depth) but the SPA does not yet send it.
- [ ] 3.3 Prefill for `me` — deferred with #3.2.
- [ ] 3.4 Surfacing `invitation.identity_mismatch` already covered by change #1.
- [ ] 3.5 Success toast covered by change #15 `surface-success-toasts-on-writes`.

## 4. Tests

- [x] 4.1 Backend integration `test_preview_endpoint_returns_safe_metadata` updated: asserts the body is exactly `{organization_name, role}` and that `email` is absent.
- [x] 4.2 Backend unit `test_accept_invitation_identity_mismatch_is_noop` from change #1 covers the mismatch path; the `confirmed_email` branch reuses the same typed error so the same test class applies.
- [ ] 4.3 Frontend Vitest "preview renders empresa + Spanish role" — deferred with #3.2.
- [ ] 4.4 Frontend Vitest "submit with mismatching email → inline alert" — deferred with #3.2.

## 5. Validation

- [x] 5.1 `openspec validate protect-invitation-preview-pii --strict` exits 0.
