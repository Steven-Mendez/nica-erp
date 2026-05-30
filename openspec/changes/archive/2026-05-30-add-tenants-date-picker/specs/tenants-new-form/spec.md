## ADDED Requirements

### Requirement: DGI validity dates use a shadcn date picker

The DGI step's `valid_from` and `valid_to` fields SHALL each
render as a `<DatePicker>` (a wrapper over shadcn `<Popover>`
+ `<Button>` trigger + `<Calendar>` content). The native
`<input type="date">` MUST be removed for both fields. The
wrapper MUST live at
`apps/web/src/components/ui/date-picker.tsx` so future
routes can reuse it.

#### Scenario: Two date pickers render in the DGI step

- **WHEN** the user advances to the Autorización DGI step
- **THEN** the rendered DOM contains exactly two trigger
  buttons whose accessible names correspond to "Válido
  desde" and "Válido hasta", and no `<input type="date">`
  element is present anywhere in the step

#### Scenario: Clicking a trigger opens the calendar popover

- **WHEN** the user clicks the "Válido desde" trigger
- **THEN** a `<Popover>` opens containing a
  `<Calendar mode="single">` with the currently-selected
  date highlighted (or the current month if no value yet)

### Requirement: Selected date displays in Spanish

The button trigger of each `<DatePicker>` SHALL render the
selected date formatted in Spanish via `date-fns/format`
with the `es` locale, MUST use the long format ("PPP") so
the month name spells out (e.g., `27 de mayo de 2026`), and
MUST fall back to a Spanish placeholder when no date is
selected (e.g., `Selecciona la fecha`).

#### Scenario: Selected date renders month name in Spanish

- **WHEN** the form value for `authorization_dgi.valid_from`
  is `"2026-05-27"`
- **THEN** the "Válido desde" trigger button displays the
  text `27 de mayo de 2026` (or the equivalent
  `date-fns` "PPP" output for the `es` locale)

#### Scenario: Empty value renders Spanish placeholder

- **WHEN** the form value is the empty string
- **THEN** the trigger button displays the Spanish
  placeholder (e.g., `Selecciona la fecha`), never an
  English string

### Requirement: Picker commits ISO YYYY-MM-DD strings to the form

The `<DatePicker>` SHALL accept a `value: string` prop
holding an ISO `YYYY-MM-DD` string (or the empty string for
"unselected") and SHALL emit `onChange: (iso: string) =>
void` with the same shape. The wrapper MUST format the
selected `Date` with `format(d, "yyyy-MM-dd")` (NOT
`d.toISOString()`, which converts to UTC and can shift the
day across timezones). The Zod `regex(/^\d{4}-\d{2}-\d{2}$/u)`
constraint on `authorization_dgi.valid_from` and
`authorization_dgi.valid_to` MUST continue to gate the form
submission.

#### Scenario: Selecting a calendar day commits an ISO string

- **WHEN** the user opens the picker for `valid_to` and
  clicks the day cell for May 27, 2026
- **THEN** the controlled form value for
  `authorization_dgi.valid_to` is the string `"2026-05-27"`
  and the Zod regex constraint passes

#### Scenario: Timezone-safe formatting

- **WHEN** the user's system clock is set to a non-UTC
  timezone (e.g., America/Managua) and the user picks the
  day cell labelled "27"
- **THEN** the committed ISO string is the same day the
  user clicked, never shifted to "26" or "28" by UTC
  conversion

### Requirement: Picker wires through React Hook Form Controller

Each `<DatePicker>` in the DGI step SHALL be wired via a
React Hook Form `<Controller>` so the form state, the Zod
resolver, and the existing `formatApiError` `loc` mapping
(`authorization_dgi.valid_from` → "Vigencia desde",
`authorization_dgi.valid_to` → "Vigencia hasta") all
continue to fire unchanged.

#### Scenario: Backend 422 on valid_from surfaces the Spanish label

- **WHEN** `POST /v1/tenants` returns 422 with detail
  `[{"loc": ["body", "authorization_dgi", "valid_from"],
  "msg": "..."}]`
- **THEN** the wizard `<Alert>` renders a message starting
  with `Vigencia desde:` (mapped by the existing
  `FIELD_LABELS` table from sprint 3.8)
