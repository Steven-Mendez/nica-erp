## Why

Two interlocking wizard bugs surfaced in the audit:

1. **F-009** — `/tenants/new` step 3 carries the chip `Opcional` but
   the Continuar button refuses to advance with the section's fields
   blank. The audit reproduced an inline alert (`Required`, also
   covered by G5) and the wizard stayed on step 3. The chip lies.
2. **F-014** — when step-2 validation fails (e.g. `Régimen` left at
   its visible placeholder while the hidden `<select>` shows a
   default), the wizard can drop the user **back to step 1** with
   step-1 fields cleared. The expected behaviour is "stay on the
   failing step and preserve all prior steps' values."

This change fixes both: step 3's schema becomes genuinely optional
(submit-with-all-blank advances to step 4), and the wizard reducer
keeps every previous step's state regardless of which step's
validation fires.

## What Changes

### Step 3 — truly optional

- `apps/web/src/routes/tenants/new.tsx` step-3 zod schema: every field
  on `authorization_dgi` becomes optional. If any field is filled, ALL
  three (`number`, `valid_from`, `valid_until`) become required (the
  "all-or-nothing" rule). The chip stays `Opcional` and the helper
  copy explains the all-or-nothing rule:
  `Si llenas uno de los campos, debes llenar los tres.`
- When the user advances with all-blank fields, the wizard SHALL
  proceed to step 4 without emitting any error.
- When the user advances with partial data, the wizard SHALL keep them
  on step 3 with Spanish field-level errors on the missing fields
  (`Obligatorio si llenas el número` or similar).

### Reducer — preserve prior steps

- Audit the wizard reducer / `useForm` hook that drives the multi-step
  flow. The current behaviour appears to be: on submit-failed, the
  reducer resets the form to its initial state and routes the user
  back to step 1.
- The correct behaviour SHALL be: on submit-failed, the reducer keeps
  the user on the failing step, with the failing step's errors set on
  the appropriate fields. Prior steps' values SHALL remain intact in
  the form state.
- Add an explicit unit test against the reducer for this invariant.

### Tests

- Frontend Vitest:
  - `/tenants/new` step 3 with all blanks → Continuar advances to
    step 4.
  - Step 3 with `number` filled but date pair blank → stays on step 3
    with Spanish field-level errors on `valid_from` and `valid_until`.
  - Step 2 with Régimen unset → stays on step 2 with the field
    error; step 1's `name` and `ruc` values remain intact when the
    user clicks Atrás after the fail.
- Browser smoke: reproduce the audit's regression — submit-with-Regimen-unset on step 2 must not regress to step 1.

## Non-goals

- The English `Required` alert (covered by G5).
- Persisting wizard state across page reloads (mentioned in the audit
  as a future improvement; out of scope here).
- Replacing the wizard with a single-page form.
