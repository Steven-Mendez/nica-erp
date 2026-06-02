## 1. DestructiveActionDialog primitive

- [ ] 1.1 Create `apps/web/src/components/dialog/destructive-action-dialog.tsx` wrapping the shadcn `<AlertDialog>` primitive with the typed props from the spec (`title`, `description`, `cancelLabel`, `confirmLabel`, `onConfirm`, `open`, `onOpenChange`).
- [ ] 1.2 Auto-focus the cancel button on open (`autoFocus` on the cancel button element).
- [ ] 1.3 Style the confirm button with the destructive variant.
- [ ] 1.4 Vitest unit test: dialog auto-focuses cancel, `Escape` closes without firing `onConfirm`, confirm activates `onConfirm` exactly once.

## 2. Wire destructive dialog into remove-member and cancel-invitation

- [ ] 2.1 Replace the direct mutation call in the remove-member button (`apps/web/src/routes/empresa/users.tsx`) with a dialog-gated flow using the documented Spanish copy.
- [ ] 2.2 Replace the direct mutation call in the cancel-invitation button with a dialog-gated flow.
- [ ] 2.3 Vitest integration: clicking remove without confirming does not issue the mutation; confirming does.
- [ ] 2.4 Vitest integration: clicking cancel-invitation without confirming does not issue the mutation; confirming does.

## 3. Cancel-invitation optimistic update

- [ ] 3.1 In `apps/web/src/features/tenants/api/hooks.ts`, update `useCancelInvitationMutation` to implement `onMutate` snapshot + `onError` rollback + `onSettled` invalidate, per the documented pattern.
- [ ] 3.2 Wire a Spanish error toast `"No se pudo cancelar la invitación."` to the `onError` path.
- [ ] 3.3 Vitest integration: confirming the dialog removes the row before the network response; a forced failure rolls back the row and toasts the Spanish copy.

## 4. Invite-member 409 + loading-state polish

- [ ] 4.1 Confirm the exact 409 problem code in `apps/api/src/contexts/tenants/adapters/inbound/http/router.py` for duplicate-pending invitations (note: pin actual code in the registry).
- [ ] 4.2 Add the duplicate-pending code → `"Esta persona ya tiene una invitación pendiente."` entry to the problem-code registry in `apps/web/src/api/errors.ts`.
- [ ] 4.3 Update `useInviteMemberMutation` so close-modal happens in `onSuccess` only; `onError` leaves the modal mounted.
- [ ] 4.4 Update the invite modal to render `<FormErrorAlert error={inviteMut.error} />` above the submit button.
- [ ] 4.5 Update the submit button to show `"Enviando…"` and `disabled` while `inviteMut.isPending`.
- [ ] 4.6 Vitest integration: MSW returns 409 with the duplicate-pending code; modal stays open, inline Spanish copy renders, form values preserved.
- [ ] 4.7 Vitest integration: pending state shows the disabled "Enviando…" button.

## 5. Members table mobile reflow

- [ ] 5.1 Update `apps/web/src/features/tenants/components/members-table.tsx` (or its actual filename — locate during implementation) to wrap the desktop `<table>` in `<div class="hidden md:block">`.
- [ ] 5.2 Add a mobile branch in `<div class="block md:hidden">` rendering each member as a `<Card>` with the documented ordering: nombre, correo, rol badge, estado badge, acciones row.
- [ ] 5.3 Render pagination controls outside both branches so they appear once and apply to both.
- [ ] 5.4 Vitest integration: render at 375×812 (using a viewport-mocking utility); assert `<table>` is not visible and cards are.
- [ ] 5.5 Vitest integration: render at 1024×768; assert `<table>` is visible.
- [ ] 5.6 Vitest integration: pagination next-page in cards layout, then resize to desktop, assert the table shows the same page.

## 6. Mobile sidebar a11y

- [ ] 6.1 In `apps/web/src/components/app-sidebar/sidebar.tsx` (or the mobile-specific file in the sidebar slice), apply `aria-hidden="true"`, `inert`, and `display: none` (via Tailwind class such as `hidden`) to the sidebar container when closed at `< 768px`.
- [ ] 6.2 Ensure all three guards are removed when the sidebar opens or the viewport widens past 768px.
- [ ] 6.3 Add `aria-controls` referencing the sidebar id and `aria-expanded` reflecting the state, plus a Spanish `aria-label` (`"Abrir menú"` / `"Cerrar menú"`) to the header trigger button.
- [ ] 6.4 Verify the shadcn `<Sheet>` (or whichever primitive is in use) provides the focus-trap when open; do not bypass it.
- [ ] 6.5 Vitest integration: at 375×812 with sidebar closed, tab order does not enter the sidebar; the trigger reports `aria-expanded="false"`.
- [ ] 6.6 Vitest integration: opening the sidebar removes all three guards and traps focus; Escape closes and returns focus to the trigger.

## 7. Cross-cutting

- [ ] 7.1 If `<FormErrorAlert>` has not yet landed via `harden-auth-flows`, introduce it here (Section 4 depends on it). Otherwise reuse the existing component.
- [ ] 7.2 Spot-check every Spanish copy string against the project's "no `tenant` in user-facing UI" rule — empresa terminology only.

## 8. Documentation

- [ ] 8.1 Update `docs/09-frontend.md` with a brief subsection on the destructive-confirm pattern (when to use the wrapper, the cancel-focus default).
- [ ] 8.2 Update `docs/09-frontend.md` with a brief subsection on the mobile-card pattern for data tables.
- [ ] 8.3 Update `docs/09-frontend.md` with a brief subsection on the closed-sidebar a11y contract (`aria-hidden` + `inert` + `display:none`). No reference to `openspec/changes/*`.

## 9. Verification

- [ ] 9.1 `pnpm --filter web typecheck && pnpm --filter web test` — green.
- [ ] 9.2 Manual smoke: at 375px, navigate to `/empresa/usuarios`, observe card layout, confirm the sidebar is not in tab order while closed.
- [ ] 9.3 Manual smoke: invite a duplicate email, confirm the modal stays open with the Spanish error.
- [ ] 9.4 Manual smoke: cancel an invitation, confirm the row disappears immediately and reappears if you force-fail the request via devtools.
- [ ] 9.5 Manual smoke: remove a member, confirm the dialog opens with cancel focused; Enter on cancel does nothing; Tab then Enter on confirm removes the member.
