## 1. Sprint doc

- [x] 1.1 Append a "Sprint follow-up — DGI date picker (sprint 3.9, 2026-05-27)" section to `docs/sprints/03-tenants-and-rls.md` after the existing 3.8 follow-up. Cover: motivation (cross-browser inconsistency + Spanish formatting), scope (only DGI step), non-goals (no range, no time, no chrono parsing, no backend change).

## 2. Install shadcn primitives

- [x] 2.1 From `apps/web/`, run `pnpm dlx shadcn@latest add calendar popover`. Confirm `apps/web/src/components/ui/calendar.tsx` and `apps/web/src/components/ui/popover.tsx` exist and that `react-day-picker`, `date-fns`, `@radix-ui/react-popover` are added to `apps/web/package.json`.

## 3. DatePicker wrapper

- [x] 3.1 Create `apps/web/src/components/ui/date-picker.tsx` exporting a `DatePicker` component with props `{ id?, value: string, onChange: (iso: string) => void, placeholder?: string, disabled?: boolean, "aria-invalid"?: boolean }`. Use `import { es } from "date-fns/locale"` and `import { format, parse } from "date-fns"`. Convert `value === ""` to `undefined` for `<Calendar selected>`. Format the trigger label as `format(date, "PPP", { locale: es })` or the placeholder. On `<Calendar onSelect>`, emit `format(d, "yyyy-MM-dd")` — NEVER `d.toISOString().slice(0,10)`.

## 4. Migrate DGI step

- [x] 4.1 In `apps/web/src/routes/tenants/new.tsx`, replace the `<Input id="valid_from" type="date" {...register("authorization_dgi.valid_from")} />` block with `<Controller name="authorization_dgi.valid_from" control={control} render={({field, fieldState}) => <DatePicker id="valid_from" value={field.value} onChange={field.onChange} placeholder="Selecciona la fecha desde" aria-invalid={fieldState.invalid} />} />`.
- [x] 4.2 Same for `valid_to` with placeholder `Selecciona la fecha hasta`.
- [x] 4.3 Import `DatePicker` from `@/components/ui/date-picker`. Keep all other imports + the existing Spanish error rendering (`errors.authorization_dgi?.valid_from`) unchanged.

## 5. Tests

- [x] 5.1 Extend `apps/web/tests/unit/routes/tenants-new.test.tsx`: advance to the DGI step (fill identity + regime + municipality), then assert (a) two trigger buttons render with accessible names matching `/Válido desde/i` and `/Válido hasta/i`, (b) clicking the "Válido desde" trigger opens a popover (`getByRole("dialog")` or `[data-state="open"]`), (c) NO `<input type="date">` is in the step DOM.
- [x] 5.2 Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`. All three must pass.

## 6. Forward-compat with sprint 3.6

- [x] 6.1 Append to the carry-over task 12.1 in `openspec/changes/welcome-onboarding-rename-members/tasks.md` an additional bullet: `<DatePicker>` for DGI `valid_from` / `valid_to` (from sprint 3.9 `add-tenants-date-picker`). Sprint 3.6's rewrite of `/organizations/new` MUST preserve this.

## 7. Smoke

- [x] 7.1 In the dev server, complete the wizard end-to-end: advance to DGI, click each date picker trigger, pick days from the calendar in Spanish, confirm the trigger buttons render dates as `27 de mayo de 2026`, complete the wizard, and verify `POST /v1/tenants` succeeds.
