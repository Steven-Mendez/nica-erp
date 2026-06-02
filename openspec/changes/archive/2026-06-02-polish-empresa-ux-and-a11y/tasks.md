## 1. DestructiveActionDialog primitive

- [x] 1.1 Create `apps/web/src/components/dialog/destructive-action-dialog.tsx` wrapping the shadcn `<AlertDialog>` primitive with the typed props from the spec (`title`, `description`, `cancelLabel`, `confirmLabel`, `onConfirm`, `open`, `onOpenChange`).
- [x] 1.2 Auto-focus the cancel button on open (`autoFocus` on the cancel button element).
- [x] 1.3 Style the confirm button with the destructive variant.
- [x] 1.4 Vitest unit test: dialog auto-focuses cancel, `Escape` closes without firing `onConfirm`, confirm activates `onConfirm` exactly once.

## 2. Wire destructive dialog into remove-member and cancel-invitation

- [x] 2.1 Replace the direct mutation call in the remove-member button (`apps/web/src/routes/empresa/users.tsx`) with a dialog-gated flow using the documented Spanish copy.
- [x] 2.2 Replace the direct mutation call in the cancel-invitation button with a dialog-gated flow.
- [x] 2.3 Vitest integration: clicking remove without confirming does not issue the mutation; confirming does.
- [x] 2.4 Vitest integration: clicking cancel-invitation without confirming does not issue the mutation; confirming does.

## 3. Cancel-invitation optimistic update

- [x] 3.1 In `apps/web/src/features/tenants/api/hooks.ts`, update `useCancelInvitationMutation` to implement `onMutate` snapshot + `onError` rollback + `onSettled` invalidate, per the documented pattern.
- [x] 3.2 Wire a Spanish error toast `"No se pudo cancelar la invitación."` to the `onError` path.
- [x] 3.3 Vitest integration: confirming the dialog removes the row before the network response; a forced failure rolls back the row and toasts the Spanish copy.

## 4. Invite-member 409 + loading-state polish

- [x] 4.1 Confirm the exact 409 problem code in `apps/api/src/contexts/tenants/adapters/inbound/http/router.py` for duplicate-pending invitations (note: pin actual code in the registry).
- [x] 4.2 Add the duplicate-pending code → `"Esta persona ya tiene una invitación pendiente."` entry to the problem-code registry in `apps/web/src/api/errors.ts`.
- [x] 4.3 Update `useInviteMemberMutation` so close-modal happens in `onSuccess` only; `onError` leaves the modal mounted.
- [x] 4.4 Update the invite modal to render `<FormErrorAlert error={inviteMut.error} />` above the submit button.
- [x] 4.5 Update the submit button to show `"Enviando…"` and `disabled` while `inviteMut.isPending`.
- [x] 4.6 Vitest integration: MSW returns 409 with the duplicate-pending code; modal stays open, inline Spanish copy renders, form values preserved.
- [x] 4.7 Vitest integration: pending state shows the disabled "Enviando…" button.

## 5. Members table mobile reflow

- [x] 5.1 Update `apps/web/src/features/tenants/components/members-table.tsx` (or its actual filename — locate during implementation) to wrap the desktop `<table>` in `<div class="hidden md:block">`.
- [x] 5.2 Add a mobile branch in `<div class="block md:hidden">` rendering each member as a `<Card>` with the documented ordering: nombre, correo, rol badge, estado badge, acciones row.
- [x] 5.3 Render pagination controls outside both branches so they appear once and apply to both.
- [x] 5.4 Vitest integration: render at 375×812 (using a viewport-mocking utility); assert `<table>` is not visible and cards are. [Deviation: jsdom does not apply CSS media queries, so the test asserts the documented class composition (`hidden md:block` + `md:hidden`) instead of computed visibility — strongest contract pinning available without a real browser.]
- [x] 5.5 Vitest integration: render at 1024×768; assert `<table>` is visible. [Deviation: same as 5.4 — covered by the class-composition assertion.]
- [ ] 5.6 Vitest integration: pagination next-page in cards layout, then resize to desktop, assert the table shows the same page. [Deferred: requires a real browser; the underlying contract — both branches share the same `table.getRowModel()` — is structurally guaranteed and exercised by the single-source-of-truth pagination assertion in `MembersTable.spec.tsx`.]

## 6. Mobile sidebar a11y

- [x] 6.1 In `apps/web/src/components/app-sidebar/sidebar.tsx` (or the mobile-specific file in the sidebar slice), apply `aria-hidden="true"`, `inert`, and `display: none` (via Tailwind class such as `hidden`) to the sidebar container when closed at `< 768px`.
- [x] 6.2 Ensure all three guards are removed when the sidebar opens or the viewport widens past 768px.
- [x] 6.3 Add `aria-controls` referencing the sidebar id and `aria-expanded` reflecting the state, plus a Spanish `aria-label` (`"Abrir menú"` / `"Cerrar menú"`) to the header trigger button.
- [x] 6.4 Verify the shadcn `<Sheet>` (or whichever primitive is in use) provides the focus-trap when open; do not bypass it.
- [x] 6.5 Vitest integration: at 375×812 with sidebar closed, tab order does not enter the sidebar; the trigger reports `aria-expanded="false"`.
- [x] 6.6 Vitest integration: opening the sidebar removes all three guards and traps focus; Escape closes and returns focus to the trigger.

## 7. Cross-cutting

- [x] 7.1 If `<FormErrorAlert>` has not yet landed via `harden-auth-flows`, introduce it here (Section 4 depends on it). Otherwise reuse the existing component.
- [x] 7.2 Spot-check every Spanish copy string against the project's "no `tenant` in user-facing UI" rule — empresa terminology only.

## 8. Documentation

- [x] 8.1 Update `docs/09-frontend.md` with a brief subsection on the destructive-confirm pattern (when to use the wrapper, the cancel-focus default).
- [x] 8.2 Update `docs/09-frontend.md` with a brief subsection on the mobile-card pattern for data tables.
- [x] 8.3 Update `docs/09-frontend.md` with a brief subsection on the closed-sidebar a11y contract (`aria-hidden` + `inert` + `display:none`). No reference to `openspec/changes/*`.

## 9. Verification

- [x] 9.1 `pnpm --filter web typecheck && pnpm --filter web test` — green (361 vitest tests, 54 files; backend 356 pytest tests).
- [ ] 9.2 Manual smoke: at 375px, navigate to `/empresa/usuarios`, observe card layout, confirm the sidebar is not in tab order while closed. [Deferred: Docker-required.]
- [ ] 9.3 Manual smoke: invite a duplicate email, confirm the modal stays open with the Spanish error. [Deferred: Docker-required.]
- [ ] 9.4 Manual smoke: cancel an invitation, confirm the row disappears immediately and reappears if you force-fail the request via devtools. [Deferred: Docker-required.]
- [ ] 9.5 Manual smoke: remove a member, confirm the dialog opens with cancel focused; Enter on cancel does nothing; Tab then Enter on confirm removes the member. [Deferred: Docker-required.]

## 10. Backend extension (added mid-change)

The proposal said "Backend: none" but the user-flagged the 409 stub-only path. Closed it end-to-end:

- [x] 10.1 New domain error `InvitationDuplicatePendingError`; `InviteMember` use case now calls `InvitationRepository.list_pending_by_email(tenant_id, email)` before adding the new row and raises the error if any match (case-insensitive).
- [x] 10.2 New port method `list_pending_by_email` on `InvitationRepository`; SQLAlchemy adapter adds the corresponding `text()` query with bind-param email; in-memory fake mirrors the contract.
- [x] 10.3 HTTP error handler maps `InvitationDuplicatePendingError → 409` with code `tenants.invitation_duplicate_pending` and the existing problem-detail shape (`apps/api/src/contexts/tenants/adapters/inbound/http/errors.py`).
- [x] 10.4 New use case `ResendInvitation` cancels the existing pending row and issues a new invitation in the same UoW; two outbox events (`tenants.InvitationCancelled` + `tenants.MemberInvited`) emitted; email re-sent.
- [x] 10.5 New endpoint `POST /v1/tenants/{tenant_id}/invitations/{invitation_id}/resend` (gated by `members:invite`).
- [x] 10.6 Pytest: `test_invite_member_rejects_duplicate_pending_invitation` (case-insensitive, idempotent on second call); `test_resend_*` (cancels + reissues, missing-invitation 410, missing-tenant 410).
- [x] 10.7 Frontend: `resendInvitation` endpoint helper (untyped escape hatch — schema regen pending, requires running backend), `useResendInvitationMutation`, "Reenviar" button next to "Cancelar" in `InvitationsTable`, success/error inline `<Alert>` copies in Spanish.
- [x] 10.8 Vitest: 3 new InvitationsTable scenarios — Reenviar fires the resend mutation, success surfaces "Invitación reenviada con un nuevo enlace.", failure surfaces "No se pudo reenviar la invitación."

Deferred / known gap:

- [ ] 10.9 Regenerate `apps/web/src/api/schema.d.ts` via `pnpm gen:api` once a backend is running locally (requires Docker); then drop the cast in `resendInvitation` and use the typed `api.POST(...)` form.
