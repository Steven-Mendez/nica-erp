## Why

Sprint 3.11 (`simplify-creation-and-empresa-rebrand`) collapsed
`/tenants/new` into a single-step form that asks only for the
empresa name. That solved the onboarding-friction problem
(operator can land on the dashboard without DGI papers in
hand) but **removed the optional path** for operators who *do*
have the data ready and would rather fill everything at once.
Hands-on testing showed both audiences exist:

- New SMB owner without DGI papers — wants to type a name and
  start using the product immediately.
- Returning operator with the DGI authorisation letter in
  front of them — wants to enter régimen, municipio,
  autorización DGI, dirección fiscal in one sitting and not
  see a "Completa los datos fiscales" banner on their first
  visit to `/dashboard`.

The fix is to bring back the four-step wizard from sprint 3.10
but make it **fully skippable**: every step renders a primary
"Continuar" button alongside a secondary "Saltar y crear"
button that POSTs whatever has been captured so far. The Zod
schema (from sprint 3.11) already marks every field except
`name` as `.optional()`, and the backend already coerces empty
fiscal fields to `None` per ADR-0034 — no contract changes
needed.

## What Changes

- Restore the four-step wizard structure at
  `apps/web/src/routes/tenants/new.tsx`:
  - Paso 1 — Identidad (`name` *required*, `ruc` optional).
  - Paso 2 — Régimen fiscal (`regime`, `municipality`,
    `is_withholder`, all optional).
  - Paso 3 — Autorización DGI (`number`, `valid_from`,
    `valid_to`, all optional).
  - Paso 4 — Dirección y resumen (`fiscal_address` optional +
    Revisión card).
- Restore the shadcn primitives previously installed
  (`Select`, `Checkbox`, `Tooltip`, `DatePicker`) and the
  sprint-3.10 polish (`RequiredMark` only on `name`,
  `onTouched` mode, `attemptedSteps`-gated errors, sectioned
  Revisión card with Badge for Retenedor and Spanish-formatted
  Vigencia).
- Add a **"Saltar y crear"** secondary button to the
  `<CardFooter>` of **every step**. Clicking it triggers
  `handleSubmit(onSubmit)` with whatever the form currently
  holds; the per-step `trigger()` gate is bypassed.
- The final step keeps the primary "Crear empresa" button;
  the "Continuar" / "Saltar y crear" pair appears on steps
  1-3.
- On step 1, the "Saltar y crear" button is **disabled until
  `name` is non-empty** (since `name` is the only required
  field). On every other step it is always enabled.
- Submission semantics stay the same as sprint 3.11: the
  backend's empty-string coercion + Optional VOs accept the
  payload as-is. The `<Alert>` banner on `/dashboard`
  continues to surface for tenants with NULL `ruc` /
  `fiscal_address`.

## Capabilities

### New Capabilities

<!-- None — extends the existing `tenants-new-form`
     capability. -->

### Modified Capabilities

- `tenants-new-form`: the route reverts from a single-step
  form to a four-step skippable wizard. Only `name` stays
  required; every other field is captured optionally across
  steps 2-4 OR skipped via the secondary submit button on
  steps 1-3.

## Impact

- Affected code:
  - `apps/web/src/routes/tenants/new.tsx` — heavy rewrite
    bringing back the wizard from sprint 3.10 with the
    skip-button addition.
- Affected tests:
  - `apps/web/tests/unit/routes/tenants-new.test.tsx` —
    rewritten: (a) on mount, Identidad step renders with
    Nombre + RUC inputs, (b) "Saltar y crear" button is
    disabled with empty name and enabled after typing a
    name, (c) clicking "Saltar y crear" from step 1 with
    only a name submits `{name, is_withholder: false}`, (d)
    walking all 4 steps and submitting the full form posts
    every field, (e) backend 422 detail rendering still
    surfaces in the wizard `<Alert>`.
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — append "Sprint
    follow-up — Skippable wizard at `/tenants/new` (sprint
    3.12, 2026-05-28)".
- Affected dependencies: none. All primitives stayed
  installed when sprint 3.11 stripped the route's body.
- No backend, no migration, no ADR. Same envelope as
  ADR-0034 (soft-creation) + ADR-0009 (shadcn stack).
