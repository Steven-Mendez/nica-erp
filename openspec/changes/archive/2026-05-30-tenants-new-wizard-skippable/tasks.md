## 1. Sprint doc

- [x] 1.1 Append "Sprint follow-up — Skippable wizard at `/tenants/new` (sprint 3.12, 2026-05-28)" section to `docs/sprints/03-tenants-and-rls.md` after the existing 3.11 follow-up. Cover motivation (both audiences exist), scope (one route), non-goals (no backend, no migration, no ADR).

## 2. Route rewrite

- [x] 2.1 In `apps/web/src/routes/tenants/new.tsx`, restore the four-step wizard structure: `STEPS` tuple = `("identity", "regime", "dgi", "address")`. Each step renders its own `<CardHeader>` + `<CardContent>` + `<CardFooter>` block, guarded by `step.key === STEPS[currentStep].key`.
- [x] 2.2 Restore the `STEP_FIELDS` map (paths per step) and the `goNext` handler that calls `await form.trigger(STEP_FIELDS[step])` then either `setCurrentStep(currentStep + 1)` or `setAttemptedSteps(prev => new Set(prev).add(step.key))` on validation failure.
- [x] 2.3 Restore the polish from sprint 3.10: `mode: "onTouched"`, `reValidateMode: "onChange"`, `touchedFields` + `isSubmitted` destructured from `form.formState`, per-field `showError(touched)` gate, `<RequiredMark />` next to `name` only (the other fields became optional per ADR-0034 / sprint 3.11).
- [x] 2.4 Restore the sectioned Revisión card on step 4: Identidad / Régimen fiscal / Autorización DGI / Dirección, `<Separator />` between sections, `<Badge>` for Retenedor, Vigencia row in `dd MMM yyyy → dd MMM yyyy` Spanish format.

## 3. Skip button

- [x] 3.1 Add a `Saltar y crear` `<Button variant="outline">` to the `<CardFooter>` of steps 1, 2, and 3 (NOT step 4). Layout: primary "Continuar" on the right, "Saltar y crear" on the left, both `type="button"`.
- [x] 3.2 The skip button's `onClick` calls `form.handleSubmit(onSubmit)()` directly. Do NOT call `await form.trigger(...)` first — bypass the per-step gate so the user can submit whatever is captured so far.
- [x] 3.3 On step 1, the skip button is disabled when `form.watch("name").trim() === ""`. On steps 2 and 3, the skip button is always enabled (reaching step 2 proves `name` was non-empty at step 1).
- [x] 3.4 Step 4's primary button keeps the existing copy `Crear empresa` and submits via `form.handleSubmit(onSubmit)` (the standard wizard-end path).

## 4. Tests

- [x] 4.1 Rewrite `apps/web/tests/unit/routes/tenants-new.test.tsx` to cover the skippable wizard:
  - (a) On mount the Identidad step renders with Nombre + RUC inputs and the `Saltar y crear` button is disabled.
  - (b) Typing a name enables `Saltar y crear` on step 1.
  - (c) Clicking `Saltar y crear` from step 1 with only a name submits `{ name: "Mi Empresa", is_withholder: false }` (plus optional empty fields).
  - (d) Walking all four steps and submitting the full form posts every field with the captured values.
  - (e) A backend 422 response renders the field-specific Spanish error in the wizard `<Alert>` via `formatApiError`.
- [x] 4.2 Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`. All three must pass.

## 5. Smoke

- [x] 5.1 In the dev server, mount `/tenants/new` and verify the Identidad step renders. Type a name, click `Saltar y crear`, verify the SPA lands on `/dashboard` with the soft-creation banner from sprint 3.11.
- [x] 5.2 Mount `/tenants/new` again, fill every field across all four steps, click `Crear empresa` on step 4, verify the SPA lands on `/dashboard` without the soft-creation banner.

## 6. Forward-compat with sprint 3.6

- [x] 6.1 Update task 12.1 in `openspec/changes/welcome-onboarding-rename-members/tasks.md` to call out the wizard-skippable behaviour as a carry-over preserved by the eventual rename: "every step (1–3) exposes a `Saltar y crear` secondary button; step 4 keeps `Crear empresa`; the skip button on step 1 is disabled while `name` is empty."
