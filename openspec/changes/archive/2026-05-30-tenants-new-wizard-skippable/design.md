## Context

Between sprint 3.10 (`polish-tenants-new-form-final`) and
sprint 3.11 (`simplify-creation-and-empresa-rebrand`),
`/tenants/new` evolved from a four-step wizard with full
fiscal capture to a single-step name-only form. The
single-step form solved the cold-start onboarding problem
([ADR-0034](../../../docs/adr/0034-empresa-product-term-and-soft-creation.md))
but punished users who *do* have the DGI letter ready and
would rather complete fiscal data in one sitting.

Both audiences exist in the field:

- **New SMB owner without papers** — types a name, lands on
  `/dashboard`, sees a "Completa los datos fiscales" banner.
- **Returning operator with DGI letter** — wants to capture
  régimen, municipio, DGI authorisation, dirección fiscal
  during creation so the first dashboard view is
  banner-free.

The Zod schema relaxation from sprint 3.11 (`name` is the
only required field; the rest are `.optional()`) already
allows partial payloads, so the contract supports the
skippable wizard without any backend change.

## Goals / Non-Goals

**Goals:**

- Restore the four-step wizard at `/tenants/new` (Identidad,
  Régimen fiscal, Autorización DGI, Dirección + resumen).
- Add a secondary "Saltar y crear" button to steps 1-3 that
  posts whatever has been captured so far, bypassing the
  per-step `trigger()` gate.
- On step 1, the "Saltar y crear" button MUST be disabled
  until `name` is non-empty (since `name` is the only
  required field).
- Preserve every sprint 3.7-3.10 ergonomic improvement:
  `mode: "onTouched"` validation, Select for Régimen and
  Municipio, Checkbox for `is_withholder`, DatePicker for
  DGI dates, Spanish error copy, info Tooltips, the
  four-section Revisión card.
- Preserve the sprint 3.11 backend coercion semantics —
  empty strings / nested empty objects round-trip as
  `None`.

**Non-Goals:**

- No backend changes. The Pydantic schemas, application
  command, repository SQL, and aggregate stay exactly as
  sprint 3.11 left them.
- No new shadcn primitives. Every component used by the
  wizard was installed in sprints 3.8/3.9.
- No new ADR. ADR-0034 (soft-creation) and ADR-0009 (shadcn
  stack) cover this change.
- No edits to other routes. The dashboard banner, account
  page, sidebar empresa switcher all stay as-is.

## Decisions

### Skip semantics: same submit, bypass per-step gate

When the user clicks "Saltar y crear", the wizard calls
`form.handleSubmit(onSubmit)` directly instead of advancing
through the per-step `trigger(STEP_FIELDS[step])` gate. The
Zod resolver still runs at submit time, so only `name`
(required) is validated; every optional field is accepted
in whatever state it happens to be in (typed, half-typed,
or empty).

This is safer than a hand-rolled skip path because RHF's
`handleSubmit` already drains any focus/blur queues and
runs the resolver — the wizard never bypasses validation,
it only bypasses the per-step gate.

### "Saltar y crear" disabled until `name` is non-empty

On step 1, `Saltar y crear` is disabled while `name` is
empty. Implemented via `form.watch("name")` rather than a
boolean state: this stays in sync with both keyboard input
and any programmatic resets without manual wiring.

On steps 2-4 the button is always enabled. The user reaches
step 2 only by successfully advancing past step 1, which
proves `name` was valid at that moment.

### Primary "Continuar" stays on the last step as "Crear empresa"

The fourth step (Dirección y resumen) keeps the primary
"Crear empresa" button — the existing copy from sprint 3.11.
"Saltar y crear" does not appear on step 4 because the user
has reached the Revisión card and is committing to submit;
the semantic distinction between "skip the rest" and "I'm
done" collapses.

## Risks / Trade-offs

- **More code path branches** — a four-step wizard with a
  skip button per step is ~600 LoC vs. ~120 for the
  single-step form. The wizard returns enough operator
  value (full fiscal capture in one sitting) to justify the
  extra surface, and the test suite covers both paths.
- **"Saltar y crear" semantics may surprise users** — a
  user who lands on step 3 and clicks "Saltar y crear"
  forfeits step 4 (Dirección y resumen). The skip button's
  copy and the empty-state dashboard banner together signal
  that data can be completed later, which lowers regret.

## Migration Plan

This is a single-route rewrite. No data migration, no
backend deploy, no feature flag. The wizard lands behind
the same `/tenants/new` URL the single-step form occupied;
the next render after deploy serves the wizard.

## Open Questions

None. The contract and adapters are stable from sprint
3.11; only the route body changes.
