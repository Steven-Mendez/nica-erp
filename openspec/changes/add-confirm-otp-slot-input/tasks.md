## 1. Sprint doc

- [x] 1.1 Append a "Sprint follow-up — `/confirm` OTP slot input (sprint 3.7, 2026-05-27)" section to `docs/sprints/03-tenants-and-rls.md`, placed after the existing 3.6 follow-up. Cover: motivation (mobile UX + paste + SMS-autofill), scope (only `/confirm`), verifiable outcome (manual smoke + tests), explicit non-goals (no wizard / no onboarding touch).

## 2. Install the shadcn primitive

- [x] 2.1 From `apps/web/`, run `pnpm dlx shadcn@latest add input-otp`. Confirm the generator creates `apps/web/src/components/ui/input-otp.tsx` and adds `input-otp` to `apps/web/package.json`. Commit the lockfile delta.
- [x] 2.2 Verify the generated file exports the four expected symbols: `InputOTP`, `InputOTPGroup`, `InputOTPSlot`, `InputOTPSeparator`. Confirm it imports `cn` from `@/lib/utils` consistent with the other primitives in `components/ui/`.

## 3. Migrate `/confirm`

- [x] 3.1 In `apps/web/src/routes/confirm.tsx`, replace the `<Input … id="code" … placeholder="123456">` inside the `code` `<Controller>` with `<InputOTP maxLength={6} value={field.value} onChange={field.onChange} onBlur={field.onBlur} autoComplete="one-time-code" inputMode="numeric" aria-invalid={fieldState.invalid} id="code">` wrapping a `<InputOTPGroup>` with six `<InputOTPSlot index={0..5}>`.
- [x] 3.2 Drop the now-redundant `placeholder` and `type="text"` props. Keep the `<FieldLabel htmlFor="code">Código de verificación</FieldLabel>` and `<FieldError>` unchanged.
- [x] 3.3 Keep the Spanish copy `Confirma tu correo`, `Ingresa el código de 6 dígitos que enviamos a tu correo`, `Confirmar`, and `Reenviar código` byte-identical.

## 4. Tests

- [x] 4.1 If a unit test exists at `apps/web/tests/unit/routes/confirm.test.tsx`, update the selectors to query six slot elements (or the hidden input by label) instead of a single `<input name="code">`. If no unit test exists, add one covering: (a) six slots render, (b) typing six digits and submitting fires the mutation, (c) paste of "123456" distributes across slots, (d) submitting fewer than six digits surfaces the field error.
- [x] 4.2 Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`. All three must pass.
- [x] 4.3 Manually smoke `/confirm` in the dev server: type six digits, paste six digits, backspace through slots, submit with five digits (expect field error), submit with six digits (expect mutation fire).

## 5. Mobile smoke

- [x] 5.1 On iOS Safari (real device or simulator) trigger a sign-up that delivers a real SMS or use the dev-mode email + manually copy the code to the clipboard. Verify the one-time-code autofill chip appears and tapping it fills all six slots. **Closed 2026-06-02**: operator validó en dispositivo real.
- [x] 5.2 Repeat on Android Chrome. Document the result in the PR description (a screenshot is sufficient). **Closed 2026-06-02**: operator validó en dispositivo real.

## 6. Wrap-up

- [x] 6.1 Update the existing `welcome-onboarding-rename-members` change's `proposal.md` only if necessary to flag that `/confirm` migration is now a separate change (no scope overlap expected, so likely a no-op — confirm by re-reading the proposal). [confirmed no-op: no `/confirm` references in that proposal]
- [x] 6.2 Open a single PR titled `feat(web): use shadcn input-otp on /confirm` referencing the sprint doc section and this OpenSpec change. **Closed 2026-06-02**: merged como parte del bundle `feat(sprint-03)` (commit `d7e85dd`); sin PR dedicado.
