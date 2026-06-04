## Why

Three audit findings cluster around the same UX gap: the SPA performs
mutations successfully but gives the user no visible confirmation.

- **F-013** — empresa creation lands on `/dashboard` with no toast.
- **F-032** — invitation send returns 201 but the dialog stays open
  with no feedback; users re-click thinking nothing happened.
- **F-042** — the invitation dialog won't close via ESC or Cancelar
  after the submit, compounding F-032.

Adding a single Sonner Toaster + wiring `onSuccess` callbacks
addresses all three.

## What Changes

### Frontend — toaster mount

- Mount `<Toaster richColors position="top-right" />` from `sonner`
  in `apps/web/src/main.tsx` (or `app.tsx`) once. Ensure it is inside
  the locale provider so Spanish copy renders correctly.
- Set the default ARIA semantics: `aria-live="polite"` (sonner does
  this by default; verify).

### Frontend — success toasts on mutations

- `apps/web/src/features/tenants/api/hooks.ts`:
  - `useCreateTenantMutation.onSuccess(data)` → `toast.success('Empresa "${data.name}" creada.')`.
  - `useSaveTenantFiscalMutation.onSuccess(data)` → `toast.success('Datos fiscales actualizados.')`.
  - `useInviteMemberMutation.onSuccess(data)` → `toast.success('Invitación enviada a ${data.email}.')` AND close the dialog.
  - `useAcceptInvitationMutation.onSuccess(data)` → `toast.success('Te uniste a ${data.organization_name}.')`.
  - `useRemoveMemberMutation.onSuccess()` → `toast.success('Miembro removido.')`.
  - `useCancelInvitationMutation.onSuccess()` → `toast.success('Invitación cancelada.')`.

### Frontend — invite dialog close behaviour

- `apps/web/src/features/tenants/components/InviteMemberDialog.tsx`:
  - `useInviteMemberMutation.onSuccess` closes the dialog
    (`setOpen(false)`) AND resets the form (`form.reset()`) AND fires
    the toast.
  - `Cancelar` button explicitly fires `setOpen(false)`. Ensure no
    pending mutation state pins the dialog open.
  - ESC key SHALL also close the dialog. Confirm Radix's
    `onEscapeKeyDown` is not being captured by a child input.

### Tests

- Vitest integration covering each mutation: MSW returns success, the
  corresponding toast renders.
- Vitest integration on invite dialog: open, submit success → dialog
  closes, toast appears, form is reset.
- Vitest integration on invite dialog: open, no submit, press ESC →
  dialog closes.
- Vitest integration on invite dialog: open, no submit, click Cancelar
  → dialog closes.

## Non-goals

- A general notifications center / persistent feed.
- Localising sonner to a different language pack.
- Animations / motion preferences (let sonner handle).
