## Why

The QA audit grouped four findings under "non-blocker but high-friction"
that all live in the same surfaces (`/empresa/usuarios` and the AppShell
chrome) and have small, well-scoped fixes that do not require backend
changes. Pulling them into a single polish change keeps the review
focused on UX/a11y guardrails without growing into a redesign.

The four findings:

1. **Destructive mutations on single click.** Remove-member and
   cancel-invitation buttons in `apps/web/src/routes/empresa/users.tsx`
   issue their mutations immediately on click. An operator who
   misclicks loses the row and has to re-issue the invite or
   re-invite the member through a separate flow.
2. **Invitation mutations are not optimistic.** The cancel-invitation
   row hangs in place for the duration of the network round-trip; the
   invite modal closes on success but does not close (or surface an
   inline error) on the 409 returned when the same email already has
   a pending invite, leaving the operator unsure what happened.
3. **Users table does not reflow on mobile.** At 375×812 the
   `<table>` overflows horizontally and the row text truncates. There
   is no card-list fallback for narrow viewports.
4. **Sidebar stays in the accessibility tree on mobile.** When the
   sidebar collapses below the responsive breakpoint, the DOM stays
   focusable. Screen readers traverse the invisible menu before the
   main content, and Tab cycles through hidden actions.

The audit's "open question" about whether removed members should stay
visible with a `Removido` badge is **not** answered here — that is a
product decision and stays in `## Open Questions` on the design doc.
This change preserves whatever the backend already returns (the
audit's reading was that removed members do come back in the list).

## What Changes

### Destructive-action confirmation

- Introduce `<DestructiveActionDialog>` under
  `apps/web/src/components/dialog/` — a thin wrapper around the
  existing shadcn `<AlertDialog>` primitive with Spanish copy slots
  for title, body, cancel-label, confirm-label, and a `destructive`
  variant on the confirm button.
- Wire it into:
  - Remove member: confirm copy `"¿Quitar a {nombre} de la empresa?"`
    body `"Perderá acceso a esta empresa de inmediato."` confirm
    `"Quitar acceso"`.
  - Cancel invitation: confirm copy `"¿Cancelar la invitación a
    {correo}?"` body `"Tendrás que volver a invitar a esta persona si
    cambias de opinión."` confirm `"Cancelar invitación"`.
- Keyboard contract: dialog auto-focuses the **cancel** button, not the
  destructive one. `Escape` dismisses. The dialog is announced by
  screen readers (the shadcn primitive already does this via
  `aria-describedby` — verify in the integration test).

### Invitation mutation polish

- `useCancelInvitationMutation` uses `onMutate` to optimistically
  remove the row from the `invitationsKey(tenantId)` cache, with
  `onError` restoring the snapshot. On success no further work is
  needed.
- `useInviteMemberMutation` gains explicit error handling for the
  `409 invitations.duplicate_pending` (or whatever the backend code
  actually is — verify against
  `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`)
  problem response. The invite modal keeps itself open and renders an
  inline `<FormErrorAlert>`: `"Esta persona ya tiene una invitación
  pendiente."`
- The invite modal's submit button shows a Spanish loading state
  (`"Enviando…"`) while the mutation is in flight and is disabled
  during that window.

### Users table mobile reflow

- Under `min-width: 768px` the existing `<table>` markup is unchanged.
- Below 768px, the table renders as a stacked card list. Each row's
  cells become labeled lines inside a `<Card>`:
  - Nombre (heading)
  - Correo (line 2)
  - Rol (badge)
  - Estado (badge)
  - Acciones (button row, full-width)
- The same React component renders both views — implemented as two
  branches inside `<MembersTable>` (Tailwind `md:hidden` /
  `hidden md:block` wrappers). No duplicate data fetch.
- Pagination controls render the same in both layouts.

### Sidebar a11y on mobile

- The mobile sidebar wrapper in
  `apps/web/src/components/app-sidebar/sidebar.tsx` (or its mobile
  variant) MUST apply `aria-hidden="true"` and `inert` (the HTML
  attribute, supported in all evergreen browsers) when the sidebar
  is collapsed below the breakpoint, AND its content MUST be
  `display: none` (not just `visibility: hidden`) so it is removed
  from the focus/AT tree entirely.
- When the sidebar is open on mobile, focus traps to the sidebar
  while the backdrop is visible (shadcn's `<Sheet>` already provides
  this — verify it's the primitive in use).
- The open/close trigger lives in the AppShell header and announces
  state via `aria-expanded` and `aria-controls`.

### Tests

- Vitest integration tests under
  `apps/web/tests/integration/` covering:
  - Remove-member cancel keeps the row; confirm fires the mutation.
  - Cancel-invitation optimistically removes the row; rollback on
    error restores it.
  - 409 duplicate-invite renders the inline error and keeps the modal
    open.
  - 320px and 375px viewport: users table renders cards, not a
    horizontally scrolling table.
  - On mobile-closed-sidebar, `aria-hidden="true"` is present and tab
    order does not enter the sidebar.

## Capabilities

### New Capabilities

- `empresa-destructive-confirmation`: the contract that all
  destructive mutations in the empresa surface MUST go through
  `<DestructiveActionDialog>` with Spanish copy and the cancel-focused
  default.
- `empresa-invitation-optimistic-updates`: optimistic-cancel
  semantics, 409 duplicate handling, modal loading state.
- `empresa-users-mobile-cards`: viewport breakpoint, card field
  ordering, button-row layout.
- `frontend-sidebar-a11y`: aria-hidden / inert / display:none rules
  for the mobile sidebar and the focus-trap contract when open.

### Modified Capabilities

_(none)_

## Impact

- **Code (frontend only):**
  - `apps/web/src/components/dialog/destructive-action-dialog.tsx` —
    new.
  - `apps/web/src/components/form/form-error-alert.tsx` — reused from
    `harden-auth-flows`; if that change has not landed, this change
    introduces it.
  - `apps/web/src/features/tenants/api/hooks.ts` —
    `useCancelInvitationMutation`, `useInviteMemberMutation`,
    `useRemoveMemberMutation` updated.
  - `apps/web/src/features/tenants/components/members-table.tsx` —
    add the mobile-card branch.
  - `apps/web/src/components/app-sidebar/sidebar.tsx` (mobile branch)
    — aria-hidden + inert + display:none when closed.
  - `apps/web/src/routes/empresa/users.tsx` — wire the dialog into
    the action buttons.
- **Tests:** under `apps/web/tests/integration/`.
- **Backend:** none.
- **APIs:** none.
- **Docs:** none required; the changes are localized to existing
  surfaces.
