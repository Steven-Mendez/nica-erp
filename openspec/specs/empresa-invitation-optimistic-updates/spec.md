# empresa-invitation-optimistic-updates Specification

## Purpose
TBD - created by archiving change polish-empresa-ux-and-a11y. Update Purpose after archive.
## Requirements
### Requirement: Cancel-invitation mutation removes the row optimistically with rollback

The `useCancelInvitationMutation` hook SHALL implement the optimistic-update pattern with snapshot rollback. The hook in `apps/web/src/features/tenants/api/hooks.ts` MUST:

- `onMutate({ invitationId, tenantId })`: cancel in-flight queries
  for `invitationsKey(tenantId)`, snapshot the current cache value,
  write a new value with the row removed, and return the snapshot.
- `onError(_err, _vars, ctx)`: restore the snapshot via
  `qc.setQueryData(ctx.queryKey, ctx.previous)` and toast the
  Spanish error copy `"No se pudo cancelar la invitación."`.
- `onSettled({ tenantId })`: invalidate `invitationsKey(tenantId)` so
  the canonical server state is reconciled.

#### Scenario: Cancel removes the row immediately

- **WHEN** the operator confirms the cancel dialog for an invitation
- **THEN** the row disappears from the table before the network response arrives

#### Scenario: Network failure restores the row and toasts the error

- **WHEN** the cancel-invitation request fails with a network error
- **THEN** the row reappears in its original position and a Spanish error toast renders

### Requirement: Invite-member mutation keeps the modal open on 409 duplicate-pending

`useInviteMemberMutation` SHALL:

- Trigger the modal close from `onSuccess` only.
- On `onError`, do nothing — the modal reads `mutation.error` and
  renders `<FormErrorAlert>` inline.

The invitations problem-code registry SHALL include the
duplicate-pending code (actual value pinned during implementation
against the backend's invitations router) mapping to the Spanish
copy `"Esta persona ya tiene una invitación pendiente."`

#### Scenario: 409 duplicate-pending keeps the modal open and renders the inline alert

- **WHEN** the operator submits an invite to an email that already has a pending invitation and the backend returns the 409 duplicate-pending problem
- **THEN** the modal remains open, the inline `<FormErrorAlert>` renders the documented Spanish copy, and the form fields retain their values

#### Scenario: Successful invite closes the modal and refreshes the pending list

- **WHEN** the invite request succeeds
- **THEN** the modal closes, the toast `"Invitación enviada."` renders, and the pending-invitations list refetches to include the new row

### Requirement: Invite-modal submit shows a Spanish loading state

The modal's submit button SHALL render a Spanish loading state while the invite mutation is in flight. While `inviteMut.isPending` is true, the button MUST:

- Display the Spanish copy `"Enviando…"` in place of the default
  `"Enviar invitación"`.
- Be disabled (so multi-click does not multi-submit).
- Render an inline spinner (or rely on the disabled state if the
  shadcn `<Button>` variant in use does not include a spinner slot).

#### Scenario: Submit button is disabled while the mutation is in flight

- **WHEN** the operator submits the invite form and the request is still in flight
- **THEN** the submit button is disabled and its label reads `"Enviando…"`

