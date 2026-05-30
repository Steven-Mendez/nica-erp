## Why

After sprints 3.7 / 3.8 / 3.9 landed Select + Checkbox +
Tooltip + DatePicker + Spanish errors + 422 surfacing on
`/tenants/new`, two ergonomic gaps remain visible enough that
the operator surfaced them on first use:

1. **Required-field error messages appear before user
   interaction.** The form runs in `mode: "onChange"`, so
   `errors.fiscal_address` ("La dirección fiscal es
   obligatoria.") and equivalents render as soon as the user
   *advances* into a step — without ever having touched the
   field. That looks like the form is shouting at the user
   for something they haven't done yet. Worse, there is no
   visual cue *in advance* that the field is required: the
   message is the *only* indicator, and it only appears once
   it's already firing.
2. **The "Revisión" summary in the final step looks
   horrible.** It's a `<dl>` with a `grid-cols-2 gap-1
   text-xs` layout sitting on a tiny `bg-muted/30` block;
   labels and values smush together, the typographic
   hierarchy is flat, and the block visually competes with
   the wizard's primary CTA. It reads as a debug dump, not a
   confirmation surface.

Both are isolated polish items on the *current*
`/tenants/new` route. Sprint 3.6 will eventually rewrite the
file to `/organizations/new`; this change extends the
sprint-3.8 carry-over so those improvements survive the
rename too.

## What Changes

- Switch the form `mode` from `"onChange"` to `"onTouched"`
  so error messages render only after a field has been
  blurred (or after the first submit attempt), not eagerly
  on mount or after step navigation.
- Add a `<RequiredMark>` (a tiny red `*` `<span
  aria-hidden="true">`) next to every required field label
  on `/tenants/new`: Nombre, RUC, Régimen, Municipio, Número
  DGI, Válido desde, Válido hasta, Dirección fiscal. The
  `is_withholder` checkbox stays unmarked (it's a boolean
  toggle, not a required text entry).
- Gate per-field error rendering with `(touchedFields.X ||
  isSubmitted)` so the message remains hidden until the user
  interacts with the field or submits — preventing the
  current "shouted error on arrival" UX. (With
  `mode: "onTouched"` this is mostly automatic, but the
  explicit guard covers the per-step `trigger()` path.)
- Redesign the Revisión panel from a `<dl>` grid into a
  proper shadcn `<Card>` (or `<div>` styled like one) with:
  - A section heading inside a `<CardHeader>` ("Revisión
    final").
  - A two-column responsive layout (`sm:grid-cols-2`) where
    each pair renders as a stacked label-then-value
    (label `text-xs uppercase tracking-wide
    text-muted-foreground`, value `text-sm font-medium`).
  - Visual separation between sections (Identidad, Régimen,
    DGI, Dirección) via `<Separator>` between groups.
  - The Vigencia range renders as a single line with the
    arrow between dates, not as two awkward columns.
  - "Sí" / "No" badge styling for `is_withholder` via shadcn
    `<Badge>` instead of the bare string.

## Capabilities

### New Capabilities

<!-- None — this change extends the existing
     `tenants-new-form` capability proposed by sprint 3.8
     and modified by sprint 3.9. -->

### Modified Capabilities

- `tenants-new-form`: form-mode contract changes to
  `onTouched`; per-field error rendering MUST be gated by
  touched-or-submitted; required field labels MUST carry a
  visible required mark; the Revisión summary's structural
  contract changes from a `<dl>` grid to a sectioned
  card-layout per the spec.

## Impact

- Affected code:
  - `apps/web/src/routes/tenants/new.tsx` —
    `mode: "onTouched"`, per-field error guards, a small
    inline `RequiredMark` component (or imported helper),
    and the new Revisión layout. No file split: keeps the
    route as one self-contained component to remain a
    drop-in for sprint 3.6's rewrite.
- Affected dependencies: none new.
- Affected tests:
  - `apps/web/tests/unit/routes/tenants-new.test.tsx` —
    extend: (a) on first render of the Address step, NO
    error message ("La dirección fiscal es obligatoria.")
    is rendered; (b) after submitting an empty Address
    step, the error IS rendered.
  - Also: assert at least one `<span>` with red text or
    `aria-hidden="true"` text content `"*"` appears next to
    each required label.
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — append a
    "Sprint follow-up — `/tenants/new` polish: required
    marks + Revisión card (sprint 3.10, 2026-05-27)"
    section.
- Sprint 3.6 carry-over: add a `polish` bullet to the
  carry-over task (task 12.1) listing `onTouched` mode,
  required-mark indicators, gated error display, and the
  card-style Revisión panel.
- No ADR. Same envelope as ADR-0009.
