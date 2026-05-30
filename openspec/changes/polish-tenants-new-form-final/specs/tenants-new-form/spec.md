## ADDED Requirements

### Requirement: Required-field labels carry a visible required mark

Every required field's `<Label>` on `/tenants/new` SHALL
sit next to a small red asterisk (`*`) rendered as a
`<span aria-hidden="true">` with `text-destructive`
styling. This applies to: Nombre, RUC, Régimen, Municipio,
Número DGI, Válido desde, Válido hasta, and Dirección
fiscal. The asterisk MUST be `aria-hidden` so screen
readers don't double-announce the required state alongside
the schema-level `aria-required` / Zod-enforced
constraint.

#### Scenario: Required asterisks visible on Identidad step

- **WHEN** the user mounts `/tenants/new`
- **THEN** the rendered DOM contains a red `*` next to the
  "Nombre" label and a red `*` next to the "RUC" label,
  both inside `<span aria-hidden="true">` elements

#### Scenario: is_withholder has no required mark

- **WHEN** the user advances to the Régimen step
- **THEN** the "Es retenedor" label has NO `*` adjacent
  (the field is a boolean toggle with a default value, not
  a required text-entry field)

### Requirement: Form validates on first touch, not on mount

The `useForm` configuration SHALL use `mode: "onTouched"`
with `reValidateMode: "onChange"`. Per-field error
messages SHALL render only when
`formState.touchedFields[field]` is true OR
`formState.isSubmitted` is true. Error messages MUST NOT
render on initial mount of a step before the user has
interacted with the field, even when an in-step
`trigger()` call has populated `formState.errors`.

#### Scenario: No error on first arrival at Address step

- **WHEN** the user advances from the DGI step to the
  Address step without typing in the Dirección fiscal
  field
- **THEN** the text "La dirección fiscal es obligatoria."
  is NOT rendered anywhere in the step

#### Scenario: Error appears after touch and reblur

- **WHEN** the user focuses the Dirección fiscal field,
  blurs it without typing anything, and triggers
  re-render
- **THEN** "La dirección fiscal es obligatoria." renders
  next to the field

#### Scenario: Error appears after submit attempt

- **WHEN** the user clicks "Crear organización" on the
  Address step with the field still empty (without ever
  having touched it)
- **THEN** "La dirección fiscal es obligatoria." renders
  (because `formState.isSubmitted` is now true)

## MODIFIED Requirements

### Requirement: Revisión summary renders as a sectioned card layout

The Address step's Revisión summary SHALL replace the
prior `<dl>` grid with a sectioned card layout. The
container MUST be a `<div>` with rounded border + padding
+ vertical spacing. The summary MUST contain four
sections, each preceded by an uppercase tracking-wide
section heading in `text-muted-foreground`:

1. **Identidad** — Nombre, RUC.
2. **Régimen fiscal** — Régimen (rendered as "General" or
   "Simplificado", not the raw enum value), Municipio,
   Es retenedor (rendered as a shadcn `<Badge>` with text
   "Sí" or "No").
3. **Autorización DGI** — Número, Vigencia (one row
   showing both dates formatted as `dd MMM yyyy` via
   `date-fns` with `locale: es`, joined by an arrow:
   `27 may 2026 → 27 may 2027`).
4. **Dirección** — Dirección fiscal.

Between consecutive sections the layout MUST render a
shadcn `<Separator>`. Within each section the fields MUST
render as stacked label-then-value pairs: label
`text-xs text-muted-foreground`, value
`text-sm font-medium`. On `sm` breakpoints and above the
fields SHOULD lay out in a two-column grid; on smaller
screens they stack.

#### Scenario: Four sections rendered with headings

- **WHEN** the user reaches the Address step's Revisión
  block
- **THEN** four distinct sections render with headings
  "Identidad", "Régimen fiscal", "Autorización DGI", and
  "Dirección" (in this order)

#### Scenario: Retenedor rendered as a Badge

- **WHEN** the user submitted `is_withholder = true` on
  the Régimen step and reaches the Revisión block
- **THEN** the Retenedor field in the Régimen fiscal
  section renders a shadcn `<Badge>` (Radix slot) with
  text "Sí"

#### Scenario: Vigencia rendered as a single line

- **WHEN** the user reaches the Revisión block with
  `valid_from = "2026-05-27"` and
  `valid_to = "2027-05-27"`
- **THEN** the Autorización DGI section renders one row
  for Vigencia displaying both dates formatted in Spanish
  (`27 may 2026 → 27 may 2027` or equivalent
  `date-fns` "dd MMM yyyy" output with `locale: es`),
  joined by an arrow character

#### Scenario: Régimen value humanised

- **WHEN** the user selected régimen `"simplified"`
- **THEN** the Régimen fiscal section's Régimen row
  displays "Simplificado", never the raw enum string
  "simplified"
