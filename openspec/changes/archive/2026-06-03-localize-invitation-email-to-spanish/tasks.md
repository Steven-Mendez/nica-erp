## 1. Template

- [x] 1.1 The invitation email is rendered inline by `_render_email` inside `apps/api/src/contexts/tenants/application/use_cases/invite_member.py` (no separate template file in the tree). Updated in place to render Spanish-first bilingual text + HTML.
- [x] 1.2 Spanish-first body text + Spanish subject prefix added per the proposal. The variables `{tenant_name}` and `{invite_url}` flow through unchanged.
- [x] 1.3 Subject now reads `nica-erp: invitación a {tenant} / invitation to {tenant}`.

## 2. Wiring

- [x] 2.1 The invite-send use case (`InviteMember.execute`) already calls `_render_email`; no rewiring required.
- [x] 2.2 No template-name changes ship — the helper stays internal to the use case.

## 3. Tests

- [x] 3.1 `test_invite_member_sends_email` extended: subject matches the bilingual prefix; text body opens with Spanish and contains both Spanish and English blocks plus expiry wording.
- [x] 3.2 The same fake-sender capture covers the integration path (the e2e tenant-lifecycle test exercises invitation send through the API end-to-end).
- [ ] 3.3 Mailpit live smoke — deferred (no live dev session in this batch run).

## 4. Validation

- [x] 4.1 `openspec validate localize-invitation-email-to-spanish --strict` exits 0.
