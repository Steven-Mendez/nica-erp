# empresa-destructive-confirmation Specification

## Purpose
TBD - created by archiving change polish-empresa-ux-and-a11y. Update Purpose after archive.
## Requirements
### Requirement: DestructiveActionDialog component wraps shadcn AlertDialog with Spanish copy and cancel-first focus

A new component at `apps/web/src/components/dialog/destructive-action-dialog.tsx` SHALL wrap shadcn `<AlertDialog>` and expose a typed API:

- `title: ReactNode` (Spanish copy slot)
- `description: ReactNode` (Spanish copy slot)
- `cancelLabel: string` (Spanish; default `"Cancelar"`)
- `confirmLabel: string` (Spanish; required, no default)
- `onConfirm: () => void`
- `open: boolean`
- `onOpenChange: (open: boolean) => void`

The dialog SHALL:

- Wrap the existing shadcn `<AlertDialog>` primitive (focus trap,
  `Escape`-to-close, `role="alertdialog"`).
- Style the confirm button with the destructive variant.
- Auto-focus the cancel button on open via `autoFocus`.
- Announce the description via the `<AlertDialogDescription>` slot so
  screen readers read it after the title.

#### Scenario: Dialog auto-focuses cancel on open

- **WHEN** `<DestructiveActionDialog open={true} ... />` mounts
- **THEN** the focused element is the cancel button, not the confirm button

#### Scenario: Escape closes the dialog without firing onConfirm

- **WHEN** the dialog is open and the operator presses `Escape`
- **THEN** `onOpenChange(false)` is invoked and `onConfirm` is NOT called

#### Scenario: Confirm fires onConfirm and closes the dialog

- **WHEN** the operator activates the confirm button
- **THEN** `onConfirm` is invoked exactly once and the dialog closes

### Requirement: Remove-member action goes through the destructive dialog

The remove-member button SHALL open a `<DestructiveActionDialog>` instead of issuing the mutation directly. The button in `apps/web/src/routes/empresa/users.tsx` MUST configure the dialog with:

- `title`: `"¿Quitar a {nombre} de la empresa?"` (templated with the
  member's display name)
- `description`: `"Perderá acceso a esta empresa de inmediato."`
- `confirmLabel`: `"Quitar acceso"`

The mutation `useRemoveMemberMutation` SHALL only fire on the
`onConfirm` callback, never on the row's direct click.

#### Scenario: Clicking the row's remove button opens the dialog

- **WHEN** the operator clicks the remove button on a member row
- **THEN** the dialog opens with the documented Spanish copy and no mutation is issued

#### Scenario: Cancelling the dialog leaves the member intact

- **WHEN** the dialog is open and the operator clicks cancel
- **THEN** the dialog closes and no `DELETE`/`PATCH` request to the member endpoint is issued

### Requirement: Cancel-invitation action goes through the destructive dialog

The cancel-invitation button in the pending-invitations table SHALL
open a `<DestructiveActionDialog>` with:

- `title`: `"¿Cancelar la invitación a {correo}?"`
- `description`: `"Tendrás que volver a invitar a esta persona si
  cambias de opinión."`
- `confirmLabel`: `"Cancelar invitación"`

The mutation `useCancelInvitationMutation` SHALL only fire on
`onConfirm`.

#### Scenario: Cancel-invitation dialog opens with templated copy

- **WHEN** the operator clicks the cancel button on a pending invitation for `"ana@example.com"`
- **THEN** the dialog opens with `"¿Cancelar la invitación a ana@example.com?"` as the title

