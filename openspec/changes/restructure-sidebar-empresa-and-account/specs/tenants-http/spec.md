## ADDED Requirements

### Requirement: Backend gap — per-user permission overrides (DROPPED — see ADR-0022 addendum 2026-05-30)

The original requirement specified `PATCH /v1/tenants/{id}/members/{user_id}/permissions` plus a `tenant_member_permissions` table to grant or revoke individual permissions per member without changing their role. The follow-up sprint never landed, and `docs/adr/0022-rbac-model.md` §"Addendum (2026-05-30) — Per-user permission overrides" formally drops the surface from the MVP.

The full text of the original requirement is preserved in the archived change history; re-promote it from there when a production tenant requests granular per-user grants.

### Requirement: `POST /v1/invitations/accept` sets `app.tenant_id` (landed 2026-05-30)

The accept endpoint `POST /v1/invitations/accept` SHALL set `set_config('app.tenant_id', '<verified token tenant_id>', true)` on its session before reading the `invitations` row, so the per-tenant RLS policy passes during invitee acceptance. Implemented at `apps/api/src/contexts/tenants/application/use_cases/accept_invitation.py` (lines 69-73); covered by `apps/api/tests/e2e/contexts/tenants/test_tenant_lifecycle.py::test_owner_walks_create_switch_invite_lifecycle`.

#### Scenario: Invitee accepts an invitation

- **GIVEN** the invitee follows the link from their invitation email
- **WHEN** the invitee POSTs to `/v1/invitations/accept`
- **THEN** the AcceptInvitation use case sets `app.tenant_id` to the verified token's tenant claim, the RLS-protected SELECT succeeds, and the response carries the new membership's `tenant_id` and `role`
