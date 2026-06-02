## Context

`/empresa/usuarios` is the densest empresa-management surface. The QA
audit found four UX/a11y issues here that share a small fix surface:

- Destructive mutations (remove member, cancel invitation) fire on
  single click.
- Invitation cancel waits for the network round-trip without
  optimistic feedback; duplicate-invite (409) closes the modal
  silently.
- The data table does not reflow to a card list on mobile.
- The mobile sidebar stays in the accessibility tree when collapsed.

All four live in the SPA only — no backend changes are needed. The
common shape: add small primitives (a destructive-confirm dialog,
mobile card rendering for the members table) and apply hygiene
conventions (aria-hidden + inert + display:none on the closed mobile
sidebar; optimistic update + 409 mapping on the invite mutations).

This change deliberately leaves the open question of whether removed
members keep showing in the table with a `Removido` status — that is
a product decision and is parked in `## Open Questions`.

## Goals / Non-Goals

**Goals:**

- A consistent destructive-confirm pattern that every destructive
  mutation in the empresa surface goes through.
- Invitation UX that gives the operator immediate feedback (optimistic
  cancel, modal loading state, inline 409 error).
- A mobile-first members table that does not require horizontal
  scrolling at 320px or 375px viewport widths.
- A mobile sidebar that is fully absent from the accessibility tree
  when collapsed.

**Non-Goals:**

- Visual redesign of the table or sidebar. Layout primitives stay
  shadcn-default.
- Bulk-action support (multi-select member rows). Defer.
- Optimistic-update infrastructure beyond the invitation flows. We
  do not optimistically remove members (the audit did not complain
  about that latency and the safer pessimistic path is fine).
- New empty-state illustrations. Spanish copy only.
- Toast-message library swap. Use the existing toast primitive.

## Decisions

### Decision 1 — `<DestructiveActionDialog>` wraps `<AlertDialog>` rather than reinventing it

The shadcn `<AlertDialog>` already provides the focus-trap, the
`Escape` close, the `role="alertdialog"`, and the announced
description text. We wrap it in a thin component that exposes:

- `title`, `description`, `cancelLabel`, `confirmLabel` as Spanish
  string props (or React-node props for templated cases like
  `"¿Quitar a {nombre}?"`).
- `variant: "destructive"` on the confirm button (red).
- An `onConfirm` callback the wrapping component fires inside.
- `defaultFocus="cancel"` (Decision 2).

This wrapper is the only API empresa routes use; the raw
`<AlertDialog>` is not consumed directly in destructive flows.

### Decision 2 — Default focus is the cancel button, not the confirm

OWASP and a11y guidance both prefer the safer default. An operator
who lands in a dialog by accident (mis-pressed Enter) should not
nuke their data by pressing Enter again. The implementation sets
`autoFocus` on the cancel button.

### Decision 3 — Optimistic cancel via `onMutate` + snapshot rollback

The pattern:

```
onMutate: async ({ invitationId, tenantId }) => {
  const queryKey = invitationsKey(tenantId);
  await qc.cancelQueries({ queryKey });
  const previous = qc.getQueryData<Invitation[]>(queryKey);
  qc.setQueryData<Invitation[]>(queryKey, (rows ?? []).filter(i => i.id !== invitationId));
  return { previous, queryKey };
},
onError: (_err, _vars, ctx) => {
  if (ctx) qc.setQueryData(ctx.queryKey, ctx.previous);
},
onSettled: (_data, _err, vars) => {
  void qc.invalidateQueries({ queryKey: invitationsKey(vars.tenantId) });
},
```

The same pattern applies to `useRemoveMemberMutation` **only if** the
audit follow-up confirms the latency is enough to feel; for now this
change leaves remove-member pessimistic per Non-Goals.

### Decision 4 — Duplicate-invite (409) keeps the modal open, renders inline alert

`useInviteMemberMutation` is updated so its `onSuccess` triggers the
modal close, and `onError` does nothing — the modal reads
`mutation.error` and renders `<FormErrorAlert>` inline. The 409 code
SHALL be confirmed against
`apps/api/src/contexts/tenants/adapters/inbound/http/router.py`
during implementation; the spec uses the placeholder
`invitations.duplicate_pending` and the implementation task pins
the actual value.

### Decision 5 — Mobile cards inside the same `<MembersTable>` component

We keep one component and branch via Tailwind classes:

- `<div class="hidden md:block">` wraps the desktop `<table>`.
- `<div class="block md:hidden">` wraps the mobile card list.

Both branches read from the same `members` array. No duplicate
fetch, no duplicate state. Pagination controls render outside both
branches and apply equally.

Considered alternatives:

- Two separate components (`MembersTable`, `MembersCardList`). More
  code, easier to drift apart. Rejected.
- A single layout that uses CSS Grid to "table-like reflow." Tried
  in prototype: the action button column wraps awkwardly and
  long emails truncate badly. Rejected.

### Decision 6 — `inert` attribute + `display: none` for the closed mobile sidebar

The HTML `inert` attribute removes a subtree from the accessibility
tree, sequential focus, and click events. We apply it in addition to
`aria-hidden="true"` (belt + braces; some legacy AT relies on
`aria-hidden`). We also apply `display: none` so the subtree is not
rendered at all by the browser; this is the strongest guarantee that
no descendant can become focused via JS.

Why all three:

- `aria-hidden`: signals to AT to skip.
- `inert`: enforces no focus, no clicks, no AT — but a single
  attribute change.
- `display: none`: removes from layout and DOM rendering — protects
  against any AT that ignores both above.

When the sidebar opens (mobile breakpoint, sheet trigger), all three
attributes are removed and the existing shadcn `<Sheet>` focus-trap
takes over.

### Decision 7 — The mobile breakpoint is 768px (Tailwind `md`)

Matches every other responsive breakpoint in the SPA. We do not
introduce a custom breakpoint for this change.

## Risks / Trade-offs

- **Risk:** Optimistic-cancel rollback flashes the row back on
  error. → **Mitigation:** the toast on error (`"No se pudo cancelar
  la invitación"`) plus the visible restore is acceptable feedback;
  better than the current "row hangs in place for 800ms."
- **Risk:** The mobile card layout makes the action menu harder to
  reach (two taps instead of one). → **Mitigation:** acceptable for
  destructive actions; the confirmation dialog already adds a tap
  anyway. Non-destructive actions (change role) get a single tap.
- **Risk:** `inert` is unsupported in older Safari. → **Mitigation:**
  the `display: none` + `aria-hidden` pair still removes the
  subtree; `inert` is the belt to the suspenders.
- **Risk:** The 409 problem code may not exist by that name in the
  backend — implementation must verify and align. → **Mitigation:**
  the implementation task explicitly checks the actual code.
- **Trade-off:** This is four small changes in one PR. We chose the
  bundle because each individually is too small to justify its own
  review pass, and they share test scaffolding for
  `/empresa/usuarios`. If review feedback splits them, that is
  acceptable — the specs are independent.

## Migration Plan

Single deploy. No data migration. Rollback is per-feature (each is
its own component or hook change).

## Open Questions

- Removed members in the table: keep them visible with a `Removido`
  badge (audit-question style) or hide them by default with a "Ver
  retirados" filter? This is a product decision and is parked.
- Should change-role also require a confirmation dialog (it is
  reversible but consequential)? Out of scope for this change.
- Should we add a "Reenviar invitación" action to pending
  invitations? The backend already supports it; defer to a separate
  UX change.
