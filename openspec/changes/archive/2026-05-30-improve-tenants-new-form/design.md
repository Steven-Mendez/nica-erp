## Context

`apps/web/src/routes/tenants/new.tsx` is a four-step wizard
for creating the first tenant. It mixes shadcn primitives
(`Card`, `Input`, `Label`, `Alert`, `Button`) with raw HTML
(`<select>`, `<input type="checkbox">`). The Zod schema in
`apps/web/src/features/tenants/schemas/index.ts` lacks explicit
Spanish messages on most constraints, so the form surfaces
English defaults like `String must contain at least 1
character(s)` when the user submits an empty field.

The backend's `Municipality` value object validates against a
fixed catalog of 17 Nicaragua departmental units
(`KNOWN_MUNICIPALITIES` in
`apps/api/src/contexts/tenants/domain/municipality.py`). The
frontend currently lets the user type any string, which then
fails server-side with no actionable feedback.

Sprint 3.6 (`welcome-onboarding-rename-members`) plans to
rewrite this wizard at `/organizations/new`. That rename
hasn't shipped yet; the operator is filing UX complaints
against the *current* route today.

## Goals / Non-Goals

**Goals:**

- Every visible error message on `/tenants/new` reads in
  Spanish.
- Régimen and Municipio fields use a real Select primitive
  with theme-aware styling, keyboard nav, and constrained
  values.
- Es retenedor is a real Checkbox with an info Tooltip
  explaining the fiscal term, plus inline Tooltips on
  Régimen and DGI número for first-time-user guidance.
- All new primitives (`select`, `checkbox`, `tooltip`) land
  through the shadcn CLI so future routes can reuse them.
- The Municipio catalog is sourced from a single frontend
  constant that mirrors the backend
  `KNOWN_MUNICIPALITIES`, preventing drift.

**Non-Goals:**

- No date-picker for DGI `valid_from` / `valid_to`. The
  native `<input type="date">` stays; only its Zod error
  message is translated. Date picker comes in a separate
  follow-up.
- No layout/wizard restructure. The four-step flow, the
  per-step Zod gating, and the final POST + switch behaviour
  stay byte-identical.
- No backend changes. The schema gains messages but keeps
  every regex / min / max constraint.
- No rename of routes. Sprint 3.6 will do that.
- Out-of-scope tooltips (e.g., on `name`, `ruc`, `fiscal
  address`) are deferred — only fiscal-jargon fields
  (Régimen, Municipio, DGI número, Es retenedor) get
  tooltips here.

## Decisions

### D1: Translate Zod errors at the schema, not at render time

**Choice:** Pass a Spanish `{ message: "..." }` to every Zod
constraint in
`apps/web/src/features/tenants/schemas/index.ts`.

**Alternative considered:** Set a global Zod `errorMap` via
`z.setErrorMap(esErrorMap)`. Rejected — the project does not
have a global locale wiring yet ([[deferred-locale-modeling]]
ADR-0033 explicitly defers locale plumbing). Per-constraint
messages are explicit, greppable, and survive any future
errorMap rollout because explicit messages always win over
errorMap defaults.

### D2: Mirror the backend municipality catalog in a single frontend constant

**Choice:** Export `MUNICIPALITIES` (an `as const` array of
17 strings) from
`apps/web/src/features/tenants/municipalities.ts`. The Select
maps over it; the Zod schema constrains
`municipality: z.enum(MUNICIPALITIES)`.

**Rationale:** A `z.enum` on the frontend gives compile-time
narrowing (`Municipality = (typeof MUNICIPALITIES)[number]`)
and a clean Zod error when a non-listed value is somehow
submitted. The single constant prevents drift between the
Select options and the schema. The backend catalog stays
authoritative — if it grows, both files update together.

### D3: Free-text fallback is *not* offered

**Choice:** Municipio is a Select with the 17 fixed options
and no "Otro" / free-text escape hatch.

**Rationale:** The backend rejects unknown values (`raise
ValueError(f"Unknown municipality ...")`), so a free-text
input here just produces a round-trip failure. If the
catalog needs to grow, that is a backend change first.

### D4: Tooltip via shadcn `tooltip` primitive, not native `title`

**Choice:** `pnpm dlx shadcn@latest add tooltip` and render
`<Tooltip>` + `<TooltipTrigger>` + `<TooltipContent>` around
an `<Info>` icon next to each fiscal-jargon label.

**Alternatives considered:**

- *Native `title` attribute on the label* — rejected: no
  mobile support, no theming, browser-decided timing.
- *Inline help text below the field* — rejected: clutters
  the wizard and the explanation is only relevant for
  first-time users; a hover/focus tooltip is the right
  affordance.

### D5: Checkbox uses shadcn `checkbox`, not Radix directly

**Choice:** `pnpm dlx shadcn@latest add checkbox`, swap
`<input type="checkbox">` for `<Checkbox>` + `<Label
htmlFor>`.

**Rationale:** Consistent with the rest of the wizard (every
other primitive is shadcn-styled). The shadcn Checkbox is a
controlled component compatible with RHF `register` via
`onCheckedChange`.

### D6: Wizard layout, copy structure, and step gating stay identical

The four-step flow, the `STEP_FIELDS` array, the per-step
`trigger(fields)` gating, the Review block, and the final
POST+switch sequence all stay byte-identical. The only file
that changes structurally is the Régimen step body and the
`is_withholder` toggle. Identity, DGI, and Address step
bodies only gain Spanish error messages and (in DGI's case)
one tooltip — they keep their inputs.

### D7: Sprint 3.6 rewrite carries this forward

A task is added to the in-flight
`welcome-onboarding-rename-members` change that, when sprint
3.6 rewrites the wizard at `/organizations/new`, the rewrite
MUST preserve the Select/Checkbox/Tooltip primitives and the
Spanish error messages established here. This keeps the
improvement from being silently regressed by the rename.

## Risks / Trade-offs

- **[Risk]** A user whose municipality is not in the
  17-entry catalog cannot create a tenant via the UI.
  **Mitigation:** The backend already rejects unknown
  municipalities; the previous free-text input never
  worked for those users either. If a real-world tenant
  surfaces a missing municipality, the catalog grows in
  one PR (backend + frontend together).
- **[Risk]** Shadcn `tooltip` requires a `<TooltipProvider>`
  ancestor. **Mitigation:** Wrap the wizard's root `<div>`
  in `<TooltipProvider delayDuration={300}>` so all tooltips
  inside the route share one provider.
- **[Risk]** Sprint 3.6 may forget to carry these
  improvements forward when it rewrites the route.
  **Mitigation:** D7 adds an explicit task to
  `welcome-onboarding-rename-members/tasks.md` referencing
  this change.
- **[Trade-off]** The Select for Municipio doesn't support
  search/filter; with 17 options that's acceptable, but if
  the catalog grows past ~25 the Select should graduate to
  a Combobox (Popover + Command). Out of scope here.

## Migration Plan

1. From `apps/web/`, run `pnpm dlx shadcn@latest add select
   checkbox tooltip`. Verify three new files in
   `components/ui/` and three new `@radix-ui/*` deps in
   `package.json`.
2. Create `apps/web/src/features/tenants/municipalities.ts`
   exporting `MUNICIPALITIES` (17 strings matching the
   backend) and the `Municipality` type.
3. Edit
   `apps/web/src/features/tenants/schemas/index.ts`: add
   Spanish messages to every constraint; tighten
   `municipality` to `z.enum(MUNICIPALITIES)`.
4. Edit `apps/web/src/routes/tenants/new.tsx`:
   - Wrap the route root in `<TooltipProvider>`.
   - Régimen `<select>` → `<Select>` composition.
   - Municipio `<Input>` → `<Select>` over
     `MUNICIPALITIES`.
   - `is_withholder` `<input type="checkbox">` →
     `<Checkbox>`.
   - Add `<Tooltip>` icons next to Régimen, Municipio, DGI
     número, and Es retenedor labels.
5. Add `apps/web/tests/unit/routes/tenants-new.test.tsx`
   with the assertions listed in the proposal.
6. Append the sprint follow-up section to
   `docs/sprints/03-tenants-and-rls.md`.
7. Update
   `openspec/changes/welcome-onboarding-rename-members/tasks.md`
   with the carry-over task (D7).
8. Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`,
   `pnpm -C apps/web lint`. Fix issues.

**Rollback:** Revert the diff (schemas, route, three new
primitives, new municipalities constant, new test, sprint
doc section). No backend, no migration state to undo.

## Open Questions

- None. Scope is intentionally tight.
