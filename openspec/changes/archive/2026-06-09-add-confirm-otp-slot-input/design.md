## Context

`apps/web/src/routes/confirm.tsx` is the screen a user lands on
after `/signup`. Cognito has just emailed them a 6-digit code
and the screen captures `(email, code)` for the call to
`POST /v1/auth/confirm-signup`. The current field is a single
`<Input type="text" inputMode="numeric"
autoComplete="one-time-code" placeholder="123456">`. The Zod
`confirmSchema` (`apps/web/src/features/auth/schemas.ts`)
validates that `code` is exactly six characters of digits.

Shadcn ships an [`input-otp`
primitive](https://ui.shadcn.com/docs/components/input-otp) —
six slot elements composed under a single hidden controlled
input. It is built on the `input-otp` npm package by
[guilhermerodz](https://github.com/guilhermerodz/input-otp),
which already implements: numeric-only enforcement, paste
distribution across slots, automatic focus advance, backspace
focus retreat, screen-reader live region for the assembled
value, and SMS-autofill compatibility (`autocomplete="one-time-
code"`).

This change swaps the `<Input>` block for `<InputOTP
maxLength={6}>` while keeping every other moving part — the
RHF `Controller`, the schema, the layout, the resend button —
identical.

## Goals / Non-Goals

**Goals:**

- Replace the plain `<Input>` with six-slot `InputOTP` in
  `confirm.tsx` so users see a code box, not a text box.
- Preserve current behaviour: RHF still owns the value, Zod
  still validates 6 digits, autocomplete one-time-code still
  fires, screen readers still announce errors via the existing
  `FieldError`.
- Establish a new capability spec `auth-frontend-confirm` that
  pins this contract so future regressions (e.g. someone
  switching to 4 slots, or breaking SMS autofill by overriding
  the autocomplete attr) are caught by spec review.
- Land the new shadcn primitive cleanly so future routes
  (forgot-password reset code, MFA in a later sprint) can reuse
  it without re-installing.

**Non-Goals:**

- No change to `/signup`, `/login`, `/forgot-password`,
  `/reset-password`, `/onboarding`, `/tenants/new`, `/welcome`
  — these are out of scope and (for the onboarding/tenant
  routes) actively being rewritten by sprint 3.6
  `welcome-onboarding-rename-members`.
- No change to the email field on `/confirm`.
- No change to the backend, Cognito wiring, the
  `useConfirmSignupMutation` / `useResendCodeMutation` hooks,
  or the `confirmSchema`.
- No change to the `Resend code` button copy or behaviour.
- No broader form-system migration (`Form`, `FormField`,
  `FormMessage`); the route stays on the `Field` + RHF
  `Controller` pattern it already uses.
- No ADR. The shadcn/ui stack is already chosen in
  [ADR-0009](../../../docs/adr/0009-frontend-stack.md); picking
  a specific shadcn primitive is not an architectural
  decision.

## Decisions

### D1: Use the shadcn `input-otp` primitive (not a hand-rolled multi-input)

**Choice:** `pnpm dlx shadcn@latest add input-otp`, which copies
a `components/ui/input-otp.tsx` file and adds the `input-otp`
npm package as a dependency.

**Alternatives considered:**

- *Hand-roll six `<Input>`s with manual focus management.*
  Rejected — paste-distribution and SMS-autofill compatibility
  are both notoriously hard to get right, and the shadcn
  primitive already solves them.
- *Use `Field` slot composition with a custom `OtpInput`
  inside.* Rejected — same maintenance cost as hand-rolling,
  with the added downside that the rest of the codebase loses
  the standard shadcn primitive when MFA / reset-code screens
  arrive later.

### D2: Slot count fixed at six, no separators

**Choice:** `<InputOTP maxLength={6}>` with one
`<InputOTPGroup>` containing six `<InputOTPSlot index={i}>`. No
`<InputOTPSeparator>`.

**Rationale:** Cognito's `ConfirmSignup` code is always 6 digits
(`CodeDeliveryDetails.CodeDeliveryDetails` for verification).
The schema already pins it. Separators add visual noise without
helping the user.

### D3: Keep RHF `Controller`, not switch to `register`

**Choice:** Wrap `<InputOTP>` inside the existing
`<Controller name="code" control={form.control} render={...}>`
block. Pass `field.value`, `field.onChange`, `field.onBlur`
through to `<InputOTP>` — the primitive is a controlled
component that already speaks `value` / `onChange`.

**Rationale:** `register` cannot bind to a custom controlled
component without `setValue` gymnastics; `Controller` is the
documented RHF pattern for non-native inputs and is what
`confirm.tsx` already uses for both fields.

### D4: Drop the `placeholder="123456"` prop

The empty slots themselves are the visual hint; a placeholder
on a slot-based component renders awkwardly because each slot
would show "1", "2", ... "6". Drop the prop. Keep the
`<FieldLabel>` text "Código de verificación" and the
description copy "Ingresa el código de 6 dígitos que enviamos a
tu correo" — those continue to carry the affordance.

### D5: Preserve autocomplete & inputMode at the InputOTP boundary

The shadcn primitive forwards arbitrary props to its underlying
hidden input. Pass `autoComplete="one-time-code"` and
`inputMode="numeric"` through so iOS/Android SMS-autofill and
the numeric keypad survive the swap. `aria-invalid` is forwarded
the same way; the `data-invalid` on the parent `<Field>` keeps
shadcn error styling consistent with the email field above.

### D6: New capability spec, not a modification

`/confirm` has no prior frontend capability spec — the only
existing frontend capability is `frontend-shell` (sprint-00
scaffold). Establishing `auth-frontend-confirm` as a new
capability is cleaner than retroactively folding confirm into
`frontend-shell` (different scope, different sprint, different
slice).

## Risks / Trade-offs

- **[Risk]** The `input-otp` npm package is a single-maintainer
  project. **Mitigation:** It is the canonical shadcn dependency
  for OTP, used by thousands of shadcn projects; bus-factor risk
  is identical to the rest of the shadcn stack. If it goes
  unmaintained, the slot abstraction is small enough (~200
  lines) to vendor.
- **[Risk]** Some SMS-autofill implementations historically had
  bugs with multi-slot OTP components, where only the first slot
  receives the autofill. **Mitigation:** The `input-otp` package
  explicitly handles this by exposing a single hidden input that
  receives the autofill and then distributes; manual smoke test
  on iOS Safari and Android Chrome is part of the verifiable
  outcome below.
- **[Risk]** Tests that look up the field by
  `getByLabelText("Código de verificación")` may stop matching
  because the label now points at a wrapper rather than a single
  input. **Mitigation:** The shadcn primitive sets the `id` on
  its hidden input; verify `getByLabelText` still resolves, or
  switch tests to `getByRole("textbox", {name: "..."})` /
  per-slot assertions.
- **[Trade-off]** The visual style of `<InputOTP>` differs from
  the surrounding `<Input>` in the email field. This is
  intentional — the code box should look different from a text
  box — but means the screen is now visually heterogeneous.
  Acceptable for the value delivered.

## Migration Plan

1. Run `pnpm dlx shadcn@latest add input-otp` from
   `apps/web/`. Inspect the generated
   `components/ui/input-otp.tsx` and the diff to
   `apps/web/package.json` (one new dep: `input-otp`).
2. Edit `apps/web/src/routes/confirm.tsx`: replace the `code`
   `Controller`'s render block (`<Input … />`) with the
   `<InputOTP maxLength={6}>` composition (D2 + D5).
3. Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`,
   `pnpm -C apps/web lint`. Fix any test selectors as needed
   (Risk #3).
4. Manual smoke: open `/confirm` in the dev server, verify keyboard
   typing distributes digits across slots, paste of "123456"
   fills all six slots, backspace retreats focus, and submit
   with a 6-digit code calls the mutation.
5. Mobile smoke (Risk #2): on iOS Safari and Android Chrome,
   trigger an SMS with a 6-digit code (or use the
   `passwordrules`/devtools simulation) and verify autofill
   populates all slots.

**Rollback:** Revert the two-file diff (`confirm.tsx` +
`components/ui/input-otp.tsx`) and the `package.json` /
`pnpm-lock.yaml` changes. No backend, schema, or migration
state to undo.

## Open Questions

- None. Scope is intentionally tiny.
