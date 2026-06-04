## Why

F-026: the audit confirmed that
`GET /v1/invitations/{token}/preview` is publicly accessible (no auth)
and returns:

```json
{"email":"accountant@audit.test","organization_name":"Empresa Auditoría Alfa","role":"accountant"}
```

The `organization_name` and `role` fields are reasonable for the
accept screen UX (the invitee needs to see what they are accepting).
The `email` is sensitive PII: anyone who obtains the link (forwarded
chat, server logs, archived mailbox, intercepted SMTP, browser
history of a shared device) learns who was being invited and to which
empresa they belong. Combined with F-015 (the now-fixed invitation
hijack), the email-disclosure compounded the risk.

This change drops the `email` field from the public preview response
and adds an explicit "Confirm your email" step to the accept screen
that is checked server-side before any membership row is created.

## What Changes

### Backend — preview response shape

- `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`:
  the `GET /v1/invitations/{token}/preview` response model SHALL be
  `{organization_name, role}` only. The `email` field SHALL be
  removed.
- `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`:
  update the response schema accordingly. Bump the OpenAPI example.

### Backend — accept-screen email retype

- `POST /v1/invitations/accept` SHALL accept an optional
  `confirmed_email` body field. When provided:
  - If `confirmed_email.casefold() != jwt.sub.casefold()`, return 403
    `invitation.identity_mismatch` (same code as G4) with the
    same Spanish title.
  - If it matches AND the authenticated user's email also matches
    (G4's existing check), proceed.
- When NOT provided, the current behaviour (after G4 lands) — bind
  to the authenticated user — applies.
- The `confirmed_email` path is an additional defense for the case
  where the SPA is showing the preview to an unauthenticated visitor
  who is about to sign up.

### Frontend — accept screen rewrite

- `apps/web/src/routes/invitations/accept.tsx`:
  - On load with `#t=<token>`, GET the preview. Render
    `Te han invitado a <organization_name> con el rol <Rol>.` (Spanish
    role via the shared `roleLabel` map from G5).
  - Render an email input pre-labelled `Confirma tu correo` with help
    text `Escribe el correo al que enviamos esta invitación.`
  - If the user is authenticated, prefill the input with their
    session email (read-only on this branch — they cannot retype an
    arbitrary value if they are already signed in).
  - On submit, call `POST /v1/invitations/accept` with
    `{token, confirmed_email}`.
- Surface the `invitation.identity_mismatch` typed error inline
  (G4's copy).

### Tests

- Backend unit: preview response no longer contains `email`.
- Backend integration: GET preview returns 200 with the documented
  shape; accept with a non-matching `confirmed_email` returns 403.
- Frontend integration: the accept screen renders the empresa name
  and the Spanish role; the email input is required.

## Non-goals

- Removing the `organization_name` field (it's needed for the accept
  UX).
- Per-link "you have one shot" enforcement beyond the existing
  invitation-status state machine (G4 still relies on jti for replay
  protection).
- Adding analytics on accept-link clicks (`organization_name` may be
  the right thing to track later, but out of scope here).
