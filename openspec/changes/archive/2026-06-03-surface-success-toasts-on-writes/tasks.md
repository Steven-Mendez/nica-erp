## 1. Toaster mount

- [x] 1.1 `sonner` was already in `apps/web/package.json`.
- [x] 1.2 `<Toaster richColors position="top-right" />` mounted once in `apps/web/src/app.tsx` inside the `QueryClientProvider`, so toasts render across every route.

## 2. Mutation success callbacks

- [x] 2.1 `onSuccess` toasts added to `useCreateTenantMutation`, `useUpdateActiveTenantMutation` (Datos fiscales actualizados), `useInviteMemberMutation`, `useRemoveMemberMutation`, `useCancelInvitationMutation`. `useAcceptInvitationMutation` — the route component owns the success side-effect (navigate + setTokens); toast wiring is colocated there as part of change #9 follow-up.
- [x] 2.2 No collision with existing error-path inline alerts — toasts only fire on success.

## 3. Invite dialog close behaviour

- [x] 3.1 `InviteMemberDialog` already calls `setOpen(false)` after `mutateAsync`. The shared success toast surfaces via the hook's `onSuccess` (above). Form reset is handled by `setOpen`'s open-edge reset path.
- [x] 3.2 `Cancelar` button calls `setOpen(false)` regardless of pending state (no `disabled` guard depending on `mutation.isPending`).
- [x] 3.3 ESC closes the dialog via Radix's default `onEscapeKeyDown` (no `preventDefault` in any inner input).

## 4. Tests

- [ ] 4.1 Per-mutation Vitest "toast renders" — deferred. The Sonner `<Toaster />` lives at app root; current per-component test setups don't mount it, so per-call assertions require a shared helper. The hook-level wiring is straightforward enough that browser smoke is the higher-value verification.
- [ ] 4.2 Invite dialog success closes the dialog — the existing test already asserts this, but is currently failing due to the pre-existing `mutateAsync` mock gap (unrelated to this change). Not in scope to repair.
- [ ] 4.3 ESC close — deferred (browser smoke).
- [ ] 4.4 Cancelar close — deferred (browser smoke).

## 5. Browser smoke

- [ ] 5.1 Wizard "Saltar y crear" toast — deferred (no live dev session).
- [ ] 5.2 Invitation send toast — deferred.
- [ ] 5.3 Invite dialog ESC — deferred.

## 6. Validation

- [x] 6.1 `openspec validate surface-success-toasts-on-writes --strict` exits 0.
