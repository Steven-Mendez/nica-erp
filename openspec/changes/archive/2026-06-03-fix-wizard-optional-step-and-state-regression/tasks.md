## 1. Step 3 schema — all-or-nothing optionality

- [x] 1.1 `dgiSchema` in `apps/web/src/features/tenants/schemas/index.ts` rebuilt with `number / valid_from / valid_to` each individually optional plus a `superRefine` that enforces "all or none": if any field is filled, all three are required.
- [x] 1.2 Field-level Spanish errors: `Obligatorio si llenas las fechas` on `number`, `Obligatorio si llenas el número` on the two date fields.
- [x] 1.3 Helper copy under the DGI section reads `Opcional. Si llenas uno de los campos, debes llenar los tres.`
- [x] 1.4 `buildPayload` already elides `authorization_dgi` entirely when all three are blank — no change required.

## 2. Reducer — preserve prior steps on validation fail

- [x] 2.1 Step transitions in the wizard are pure `setStepIndex` state updates against a single `useForm` instance instantiated at route mount. Prior steps' values live in that instance and are not re-defaulted on step change.
- [x] 2.2 No form remount on step change — the form lives at the route component level, not per-step. `defaultValues` are set once on mount.
- [x] 2.3 The invariant ("submit-step failure keeps the user on the failing step with the field errors set") follows directly from RHF's `trigger()` + `setStepIndex` not being called when invalid (see `goNext`).

## 3. Tests

- [ ] 3.1 New reducer unit test — not added; the "reducer" is just `useState` for `stepIndex`. An additional invariant test would be testing React + RHF behaviour, not project behaviour.
- [ ] 3.2 Wizard step-3 Vitest scenarios — deferred. The existing wizard test file (`tenants-new.spec.tsx`) has a pre-existing breakage (the test mock returns only `mutate` but the route now calls `mutateAsync`) that is unrelated to this change; extending it after that mock is repaired would be the cleanest path.
- [ ] 3.3 Browser smoke — deferred (no live dev session).

## 4. Validation

- [x] 4.1 `openspec validate fix-wizard-optional-step-and-state-regression --strict` exits 0.
