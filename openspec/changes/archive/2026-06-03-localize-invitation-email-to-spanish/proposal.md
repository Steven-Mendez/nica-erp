## Why

F-024: the invitation email Mailpit captured during the audit is
**English-only**:

```
Subject: Invitation to Empresa Auditoría Alfa on nica-erp
Body:    You have been invited to join Empresa Auditoría Alfa on nica-erp.
         Accept here: http://localhost:5173/invitations/accept#t=…
         This link expires in 7 days.
```

This violates the project's Spanish-UI rule. Signup / OTP confirmation
emails are bilingual (Spanish + English co-equal), but invitation
emails are English-only. SMB recipients in Nicaragua are not assumed
to read English.

This change rewrites the invitation email template to mirror the
bilingual structure of the signup email — Spanish first, English as a
secondary block — so the rule is honored without breaking any current
English-only operator's habit. (A "drop English entirely" variant is
called out as a non-goal, gated by user policy.)

## What Changes

### Backend — bilingual email template (Spanish primary)

- `apps/api/src/contexts/identity/adapters/outbound/email/templates/` (or
  the equivalent tenants-context templates dir): add or update the
  invitation template so the rendered text body opens with Spanish:
  ```
  Invitación a {{tenant_name}} en nica-erp

  Has sido invitado a unirte a {{tenant_name}} en nica-erp.

  Acepta aquí (expira en 7 días):
  {{accept_url}}

  Si no esperabas esta invitación, puedes ignorar este mensaje.

  ---
  Invitation to {{tenant_name}} on nica-erp
  You have been invited to join {{tenant_name}} on nica-erp.
  Accept here (expires in 7 days): {{accept_url}}
  If you did not expect this invitation, you can ignore this email.
  ```
- Subject SHALL be bilingual:
  `nica-erp: invitación a {{tenant_name}} / invitation to {{tenant_name}}`
- HTML variant (if shipped) mirrors the same Spanish-first structure
  with the same expiry wording.

### Tests

- Backend unit test in `apps/api/tests/unit/contexts/tenants/email/`:
  rendered subject starts with `nica-erp: invitación a` and body's
  first non-blank line contains `Invitación a`.
- Backend integration test (real send through the
  EmailSender stub): captured outbox payload's body contains both
  language blocks.

## Non-goals

- Switching to a per-user locale (every recipient gets the same
  bilingual template).
- HTML email overhaul / rebranding.
- Localizing emails other than the invitation (signup/OTP/forgot are
  already bilingual — see F-004 for a future consistency pass).
