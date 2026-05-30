## Context

`apps/web/src/routes/tenants/new.tsx` uses RHF with
`mode: "onChange"` and renders per-field errors
unconditionally whenever `errors.X` is populated. The form
also calls `trigger(fields)` on each step's "Continuar" to
gate forward navigation — that call marks fields as
errored without first marking them as touched, so when the
user lands on a later step, the errors from the gate run
remain in `formState.errors` until the field is edited.

The Revisión panel is a `<dl>` grid that visually
competes with the primary CTA and reads as a debug dump.

## Goals / Non-Goals

**Goals:**

- Required-field errors never appear before the user has
  interacted with the field or submitted the form.
- Every required field carries a small red `*` next to its
  label so the user knows it's required *in advance*.
- The Revisión panel reads as a confirmation surface, not a
  debug dump: sectioned, properly typographed, with
  semantic emphasis on the values.

**Non-Goals:**

- No change to the wizard's step structure, per-step
  trigger gating, or POST + switch flow.
- No change to the Zod schemas, the backend, or the API
  client.
- No move to a new form library, no formik-style API
  layer, no global field-error abstraction. Inline guards
  are enough for this single route.
- No global "required mark" component. A small inline
  `RequiredMark` inside this route is the right size for
  the scope; promoting it to `components/ui/` happens when
  a second route needs it.

## Decisions

### D1: Form mode `onTouched`, not `onSubmit` or `onBlur`

**Choice:** `useForm({ mode: "onTouched",
reValidateMode: "onChange" })`.

**Rationale:** `onTouched` validates a field the first
time it loses focus, then on every change thereafter (via
`reValidateMode`). This gives the user immediate feedback
*after* they've engaged with a field, but never before.
`onSubmit` would defer all feedback until the final
submit, which loses the live-correction UX the user
expects from a wizard. `onBlur` would not re-validate as
the user types after a failed validation, leaving stale
errors.

### D2: Explicit per-field touched-or-submitted guard

**Choice:** Wrap each error block:
```
{(touchedFields.X || isSubmitted) && errors.X && (
  <p className="text-xs text-destructive">{errors.X.message}</p>
)}
```

**Rationale:** `mode: "onTouched"` already prevents
*validation* before touch, but the `trigger()` call on
"Continuar" forces validation across an entire step
including untouched fields. Without the guard, advancing
through Identidad → Régimen → DGI → Address pre-validates
`fiscal_address` and the error renders on arrival. The
guard makes the user-facing error rendering *independent*
of when the underlying RHF state happened to be
populated.

### D3: Inline `RequiredMark`, not a shared primitive

**Choice:**
```tsx
const RequiredMark = () => (
  <span aria-hidden="true" className="text-destructive">*</span>
);
```
Defined at module scope in `new.tsx`.

**Rationale:** This is the only route in the codebase that
needs it today. Promoting to `components/ui/` adds an
import surface for a one-line component nobody else
consumes yet. When sprint 3.6's rename happens or sprint
4+ adds a second form, graduate it then.

The `aria-hidden="true"` keeps the asterisk out of the
screen-reader announcement; the required semantic comes
from the field's `aria-required` attribute (passed via
the underlying primitive's `required` prop where
relevant) or from the Zod schema's `min(1)` constraint
surfacing on submit.

### D4: Revisión layout — sectioned card with section headings

**Choice:** A `<div>` with `border rounded-lg p-4
space-y-4`, containing four sections (Identidad, Régimen,
DGI, Dirección), each section:
```
<div>
  <h3 className="text-xs uppercase tracking-wide text-muted-foreground mb-1.5">Identidad</h3>
  <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-1.5">
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">Nombre</dt>
      <dd className="text-sm font-medium">{getValues("name")}</dd>
    </div>
    ...
  </dl>
</div>
```
Sections separated by `<Separator />`.

**Rationale:**

- A `<Card>` ancestor would conflict with the wizard's
  outer `<Card>`; a `<div>` styled card-like is cleaner.
- Stacked label-then-value gives each datum visual
  breathing room and a clear hierarchy (uppercase tiny
  label, medium value).
- Sections match the wizard's mental model (Identidad,
  Régimen, DGI, Dirección) — the user reviews them in the
  same order they filled them.
- `<Separator />` between sections, not borders inside
  each row, keeps the visual rhythm light.

### D5: Boolean field rendered as a Badge

**Choice:** `<Badge variant={is_withholder ? "default" :
"secondary"}>{is_withholder ? "Sí" : "No"}</Badge>` for
the Retenedor row.

**Rationale:** A bare string "sí" / "no" reads as
placeholder text. A badge gives the boolean state a
distinct visual treatment matching the rest of the
shadcn-styled surfaces.

### D6: DGI vigencia as a single line

**Choice:** Render "Vigencia" as one row with both dates
formatted in Spanish (`format(date, "dd MMM yyyy", {
locale: es })` → `27 may 2026`), joined by an em arrow:
```
27 may 2026 → 27 may 2027
```

**Rationale:** The two dates are a logical range, not two
independent facts. Showing them on one line with an arrow
between them matches how a user thinks about the
authorisation's validity. The shorter `dd MMM yyyy` mask
(vs. the picker's full `PPP`) keeps the row compact in
the review.

### D7: Modify the existing capability, do not create a new one

This change ships MODIFIED deltas on the
`tenants-new-form` capability. The two affected
requirement areas (form-error rendering / Revisión
panel) already exist as ADDED requirements from sprints
3.8 / 3.9; MODIFIED includes the full updated text per
OpenSpec rules.

## Risks / Trade-offs

- **[Risk]** The `RequiredMark` next to the
  `<TooltipProvider>` and the info `<Tooltip>` icons on
  Régimen / Municipio / DGI número / Es retenedor needs
  to coexist visually. **Mitigation:** Lay out the label
  row as `<div className="flex items-center gap-1.5">`
  with the `<Label>`, the `<RequiredMark>` (where
  applicable), then the `<InfoTip>`. Order matters: label,
  required mark, info icon.
- **[Risk]** `mode: "onTouched"` may surprise users who
  click "Continuar" without ever touching a field —
  `trigger()` still validates but the error shows up only
  after submission gating. **Mitigation:** `trigger()`
  also marks the validated fields as touched per RHF
  docs (need to verify; if not, call
  `trigger(fields, { shouldFocus: true })` and live with
  the focus side-effect — focus on the first invalid
  field is desirable anyway).
- **[Trade-off]** The redesigned Revisión panel is taller
  than the old `<dl>`. Acceptable: the wizard already
  scrolls, and a confirmation surface deserves vertical
  space.

## Migration Plan

1. Edit `apps/web/src/routes/tenants/new.tsx`:
   - Add `mode: "onTouched"` to the `useForm` config (and
     `reValidateMode: "onChange"`).
   - Destructure `touchedFields` and `isSubmitted` from
     `formState`.
   - Define a tiny `RequiredMark` component at module
     scope.
   - Add `<RequiredMark />` next to every required field's
     `<Label>`. Lay out as
     `<div className="flex items-center gap-1.5">`.
   - Wrap each error block in
     `{(touchedFields.<path> || isSubmitted) && errors.<path> && (...)}`.
   - Replace the Revisión `<dl>` block with the sectioned
     card layout (D4 + D5 + D6).
   - Import `Separator` from `@/components/ui/separator`
     and `Badge` from `@/components/ui/badge` (both
     already installed).
   - Import `format` and `es` (already imported via
     `date-picker.tsx`; need them here too).
2. Edit
   `apps/web/tests/unit/routes/tenants-new.test.tsx` with
   the new scenarios.
3. Append the sprint 3.10 follow-up to
   `docs/sprints/03-tenants-and-rls.md`.
4. Append a polish bullet to sprint 3.6's carry-over task.
5. `pnpm -C apps/web test|typecheck|lint`. All green.

**Rollback:** Revert the diff to `new.tsx`, the test
file, the sprint doc section, and the carry-over bullet.
Single-file change otherwise.

## Open Questions

- None.
