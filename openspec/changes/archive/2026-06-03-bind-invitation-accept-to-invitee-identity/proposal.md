## Why

The 2026-06-03 audit (F-015) reproduced a critical OWASP A01 broken
access control bug: any logged-in user who obtains an invitation link
can join the empresa as themselves by calling
`POST /v1/invitations/accept` — the handler decodes `tenant_id` and
`role` from the JWT but does NOT compare the JWT's `sub` (the invitee
email at issue time) against the authenticated user's email. Live
repro: owner2@audit.test accepted a link that was issued to
accountant@audit.test, and `GET /v1/tenants/me` then listed the
empresa with role `accountant` for owner2.

This change adds the missing identity binding and a typed
`invitation.identity_mismatch` error.

## What Changes

### Backend — identity binding

- `apps/api/src/contexts/tenants/application/use_cases/accept_invitation.py`
  (or wherever the accept handler lives):
  - SHALL extract `jwt.sub` (the invitee's email at issue time) from
    the verified invitation token.
  - SHALL fetch the authenticated user's email from the current
    request principal.
  - SHALL compare `jwt.sub.casefold() == principal.email.casefold()`.
  - On mismatch, SHALL raise `InvitationIdentityMismatchError`.
  - On match, the existing accept logic proceeds.
- `apps/api/src/contexts/tenants/domain/errors.py` (or
  `application/errors.py`):
  - New typed error `InvitationIdentityMismatchError` with
    `code:"invitation.identity_mismatch"`.
- `apps/api/src/contexts/tenants/adapters/inbound/http/errors.py`:
  - Map `InvitationIdentityMismatchError` to `403 Forbidden` with
    Spanish title `Esta invitación no es para ti` and
    `code:"invitation.identity_mismatch"`. Detail copy SHALL NOT leak
    the JWT sub to the requester.

### Frontend — typed error copy

- `apps/web/src/api/errors.ts` problem-code registry:
  - Add `invitation.identity_mismatch` →
    `"Esta invitación es para otra persona. Cierra sesión y entra con
    el correo invitado."`.
- `apps/web/src/routes/invitations/accept.tsx`:
  - Render `FormErrorAlert` for the typed error code with the message
    above; offer a "Cerrar sesión" button that calls
    `/v1/auth/logout` and routes to `/login?invite=…` so the user can
    sign in or sign up under the invited email.

### Tests

- Backend unit:
  - Valid match → success returns `{tenant_id, role}`.
  - JWT.sub mismatch (different case, different email) → typed error
    raised.
- Backend integration:
  - Repro the audit: invite `accountant@audit.test`, log in as
    `owner2@audit.test`, POST accept → 403 with typed code.
- Frontend integration (MSW):
  - 403 with `invitation.identity_mismatch` renders the documented
    Spanish copy; the row does NOT appear in `/v1/tenants/me`.

## Non-goals

- Restricting the anonymous preview (`GET /v1/invitations/{token}/preview`)
  — that is owned by `protect-invitation-preview-pii` (G9).
- Removing case-insensitivity (the comparison stays case-insensitive
  so `Owner@…` and `owner@…` are treated as the same identity).
- Letting unauthenticated users see a "this isn't for you" screen —
  the existing `401 Missing or malformed Authorization header` path
  on `/v1/invitations/accept` is fine.
