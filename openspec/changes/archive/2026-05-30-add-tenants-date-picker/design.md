## Context

After sprint 3.8 the `/tenants/new` wizard has Select +
Checkbox + Tooltip in the Régimen step and surfaces 422
detail in Spanish — but the Autorización DGI step still uses
two native `<Input type="date">` elements. The native input
renders inconsistently across browsers (white pill on macOS
Safari, OS-themed dialog on Chrome, no theme support
anywhere), and its labels and month names are forced to the
OS locale rather than Spanish.

The backend Pydantic schema (`AuthorizationDgiPayload`)
accepts `valid_from: date` and `valid_to: date`, parsing ISO
`YYYY-MM-DD` strings transparently. The frontend Zod schema
constrains both with `regex(/^\d{4}-\d{2}-\d{2}$/u)`. As long
as the new picker emits ISO strings, no schema or backend
change is needed.

Context7 (`/websites/ui_shadcn`) confirms the canonical
shadcn date-picker recipe: `<Popover>` triggered by a
`<Button>` that displays `format(date, "PPP")` (or any
`date-fns/format` mask), with `<Calendar mode="single"
selected={date} onSelect={...}>` inside.

## Goals / Non-Goals

**Goals:**

- Two `<DatePicker>` controls replace the native `<input
  type="date">` elements for `valid_from` and `valid_to`.
- Visible date labels are formatted in Spanish, e.g.
  `27 may 2026`, via `date-fns/locale/es`.
- The form continues to hold ISO `YYYY-MM-DD` strings, so
  the existing Zod regex, the backend Pydantic parser, and
  the sprint-3.8 `formatApiError` `loc` mapping all stay
  unchanged.
- The picker primitive lands as a reusable
  `components/ui/date-picker.tsx` so future routes
  (invoice issue date, payment date, etc.) compose it
  directly.

**Non-Goals:**

- No range picker. `valid_from` and `valid_to` stay as two
  independent single-date pickers. (A range picker is a
  separate primitive — `<Calendar mode="range">` — and the
  two-input layout is already familiar.)
- No natural-language parsing (`chrono-node`). The popover
  + calendar is the only interaction; users do not type.
- No time picker. DGI dates are date-only.
- No backend changes — Pydantic still receives ISO strings.
- No date-validation tightening beyond what sprint 3.8
  already did (the existing `valid_to >= valid_from`
  invariant lives in the `AuthorizationDgi` VO and produces
  500-shaped errors today; that's a separate sprint).

## Decisions

### D1: Canonical popover + calendar pattern, not natural-language input

**Choice:** Use the simpler shadcn pattern (Popover + Button
trigger + Calendar inside) rather than the
`chrono-node`-backed natural-language variant.

**Rationale:** The DGI dates are short-lived bureaucratic
metadata; the user copies them from the DGI authorisation
letter. Free-text parsing adds complexity without solving
a real problem here.

### D2: ISO string in the form, Date in the calendar

**Choice:** The wrapper accepts a `value: string`
(`YYYY-MM-DD` or `""`) and emits `onChange: (iso: string)
=> void`. Internally it converts to/from `Date` for the
Calendar.

**Rationale:** RHF + Zod operate on the ISO string the
backend expects. Keeping the wire format authoritative
means no `valueAsDate` gymnastics, no timezone surprises
(JS `Date` parsing of bare `YYYY-MM-DD` is UTC midnight; we
treat the picker as date-only and never carry time).

### D3: Spanish formatting via date-fns locale

**Choice:** Format the displayed date with
`format(date, "PPP", { locale: es })`, e.g.
`27 de mayo de 2026`.

**Rationale:** [[feedback_spanish_ui]] mandates Spanish for
user-visible text. `date-fns` ships an `es` locale that
covers month / weekday names; the Calendar component's
`locale` prop accepts the same locale object for its
header.

### D4: Wrapper in `components/ui/`, not in
`features/tenants/`

**Choice:** `apps/web/src/components/ui/date-picker.tsx`,
alongside the other shadcn primitives.

**Rationale:** The date picker is cross-feature
infrastructure (invoices, payments, kardex backdating will
all use it). Keeping it in `components/ui/` is consistent
with how `select.tsx`, `checkbox.tsx`, etc. live.

### D5: Controller integration, not register

**Choice:** Wire each `<DatePicker>` via RHF
`<Controller>`.

**Rationale:** `register` only binds to native form
elements. The picker is a controlled component identical
in shape to the Select / Checkbox already wired with
`Controller` in sprint 3.8 — uniformity matters.

### D6: Modify the existing `tenants-new-form` capability

**Choice:** This change ships a MODIFIED delta on the
`tenants-new-form` capability (the date-input requirement)
rather than a new capability. The DGI dates are part of the
same form contract.

**Rationale:** The form is one logical surface; splitting
it across two capabilities would force consumers to read
both specs to know what `/tenants/new` does. Per OpenSpec
rules, MODIFIED includes the full updated requirement
content.

### D7: Sprint 3.6 carry-over extends, not creates

The existing carry-over task in sprint 3.6's `tasks.md`
(section 12, added by sprint 3.8) gains one extra bullet
listing `<DatePicker>` as a primitive that must survive the
rename. Same pattern, one-line edit.

## Risks / Trade-offs

- **[Risk]** `react-day-picker` and `date-fns` are
  non-trivial bundle weight (~30 kB gzipped combined).
  **Mitigation:** Both are tree-shakeable; we import only
  `format` from `date-fns` and only the day-picker
  component the Calendar primitive uses. Sprint 04+ will
  reuse them, amortising the cost.
- **[Risk]** ISO ↔ Date conversion in the wrapper has to
  handle the empty-string case (initial mount before user
  picks anything). **Mitigation:** Return `undefined`
  for `selected` when value is `""`, and render the
  placeholder label.
- **[Risk]** Calendar inside Popover in a tall scrollable
  Card may collide with the bottom of the viewport.
  **Mitigation:** Popover already auto-flips via Radix's
  collision detection; verify in the smoke test.
- **[Trade-off]** Two independent pickers don't enforce
  `valid_from <= valid_to` client-side. The backend VO
  enforces it (and ships a 500 today, not 422). Tightening
  that into a cross-field Zod refinement is out of scope.

## Migration Plan

1. From `apps/web/`, run `pnpm dlx shadcn@latest add
   calendar popover`. Confirm two new files in
   `components/ui/` and three new deps in `package.json`
   (`react-day-picker`, `date-fns`, `@radix-ui/react-
   popover`).
2. Create
   `apps/web/src/components/ui/date-picker.tsx` exporting
   `DatePicker` with `value: string`, `onChange: (iso:
   string) => void`, `id?: string`, `placeholder?: string`,
   `disabled?: boolean` props. Internally:
   ```
   const date = value !== "" ? new Date(`${value}T00:00:00`) : undefined;
   const label = date ? format(date, "PPP", { locale: es }) : (placeholder ?? "Selecciona una fecha");
   ```
   Calendar `onSelect={(d) => onChange(d ? toISO(d) : "")}`
   where `toISO` returns the local-date `YYYY-MM-DD` string
   (use `format(d, "yyyy-MM-dd")` — NOT `d.toISOString()`,
   which converts to UTC and can shift the day).
3. Edit `apps/web/src/routes/tenants/new.tsx`'s DGI step:
   replace each `<Input id="valid_from" type="date" ...>`
   with `<Controller name="authorization_dgi.valid_from"
   control={control} render={({field}) => <DatePicker
   id="valid_from" value={field.value}
   onChange={field.onChange} placeholder="Selecciona la
   fecha desde" />}>`. Same for `valid_to`.
4. Extend `tests/unit/routes/tenants-new.test.tsx`: assert
   that the DGI step renders two date-picker buttons whose
   accessible names match the labels "Válido desde" and
   "Válido hasta", and that clicking the trigger toggles
   the popover open.
5. Append the sprint 3.9 follow-up section to
   `docs/sprints/03-tenants-and-rls.md`.
6. Add the `<DatePicker>` bullet to sprint 3.6's
   carry-over task in
   `openspec/changes/welcome-onboarding-rename-members/tasks.md`
   (item 12.1).
7. Run `pnpm -C apps/web test|typecheck|lint`. All green.

**Rollback:** Revert the diff: two new primitive files
(calendar, popover), the new `date-picker.tsx` wrapper, the
DGI step body in `new.tsx`, the package.json/lockfile
additions, the sprint doc section, and the carry-over
bullet.

## Open Questions

- None.
